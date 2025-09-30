from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
# --- NEW FEATURE: Import libraries for Auth, Hashing, and File System ---
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_talisman import Talisman
from werkzeug.security import generate_password_hash, check_password_hash
import hashlib
# ---
from dotenv import load_dotenv  # Import the load_dotenv function
from sentence_transformers import SentenceTransformer
import json
from datetime import datetime
from rank_bm25 import BM25Okapi
import logging
import re
import os
import traceback
# Import our custom modules
from resume_parser import UniversalResumeParser
from pdf_extractor import DocumentExtractor
import google.generativeai as genai

# --- NEW: Import Flask-Mail ---
from flask_mail import Mail, Message

# --- Gemini API Configuration ---
# DEPLOYMENT FIX: This is the critical change. We are explicitly setting the API endpoint.
GEMINI_API_KEY = os.environ.get("GOOGLE_API_KEY")
if GEMINI_API_KEY:
    try:
        client_options = {"api_endpoint": "generativelanguage.googleapis.com"}
        genai.configure(api_key=GEMINI_API_KEY, client_options=client_options)
        print("Gemini API configured successfully with custom endpoint.")
    except Exception as e:
        print(f"Error configuring Gemini API: {e}")

# DEPLOYMENT: Load environment variables from a .env file. This is crucial for managing secret keys like the database URL.
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

Talisman(app, content_security_policy=False)

# --- NEW, PRODUCTION-READY CORS SETUP ---
# Get the allowed origins from an environment variable.
# The variable should contain comma-separated URLs (e.g., "http://localhost:3000,https://your-site.netlify.app")
allowed_origins = os.environ.get("ALLOWED_ORIGINS", "").split(",")

# If the list is empty or something goes wrong, have a sensible default for development.
if not allowed_origins or allowed_origins == ['']:
    allowed_origins = [r"http://localhost:3000"] # A default for local testing

print(f"CORS enabled for the following origins: {allowed_origins}")

# --- ADD THIS LINE ---
CORS(app,
     origins=allowed_origins,
     supports_credentials=True)

# --- NEW FEATURE: Add a secret key for session management ---
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "a-super-secret-key-for-development")

# --- ADD THIS LINE ---
app.config['UPLOAD_FOLDER'] = 'uploads'
# ---
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'None'

# --- Database Configuration ---
# DEPLOYMENT: Configure SQLAlchemy to connect to the database.
# It reads the database URL from an environment variable ('DATABASE_URL').
# If it's not found, it defaults to a local SQLite file named 'resumes_dev.db' for development.
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL", "sqlite:///resumes_dev.db")
# DEPLOYMENT: Disable a SQLAlchemy feature that adds overhead, which is not needed here.
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- NEW: Configure Flask-Mail from environment variables ---
app.config = os.getenv('MAIL_SERVER')
app.config = int(os.getenv('MAIL_PORT', 587))
app.config = os.getenv('MAIL_USE_SSL', 'False').lower() in ['true', '1', 't']
app.config = os.getenv('MAIL_USE_TLS', 'True').lower() in ['true', '1', 't']
app.config = os.getenv('MAIL_USERNAME')
app.config = os.getenv('MAIL_PASSWORD')
# ---

# --- NEW FEATURE: Setup Flask-Login ---
login_manager = LoginManager()
login_manager.init_app(app)
# DEPLOYMENT: Initialize the SQLAlchemy object, which we will use for all database operations.
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# --- NEW: Initialize Mail instance ---
mail = Mail(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
# ---

print("Loading sentence transformer model...")
model = SentenceTransformer('all-mpnet-base-v2')
parser = UniversalResumeParser()
extractor = DocumentExtractor()
print("All components loaded successfully!")

# This prompt will now be used by both functions
RESUME_KWD_EXTRACTION_PROMPT = """
    CRITICAL: You MUST return ONLY valid JSON. NO explanations, NO additional text, NO markdown formatting.

    === TASK: STRICT KEYWORD EXTRACTION FROM RESUME FOR DIRECT MATCHING ===
    Extract ALL **explicitly mentioned** keywords from the resume. This system prioritizes the literal presence of terms for direct, exact string matching. DO NOT infer, generalize, or semantically expand beyond the explicit text.

    === REQUIRED JSON OUTPUT FORMAT ===
        {{
            "hard_skills": [],
            "tools_and_platforms": [],
            "methodologies_and_frameworks": [],
            "qualifications": [],
            "experience_indicators": []
        }}

        === ESSENTIAL KEYWORD CATEGORIES ===

        1. **hard_skills**: Specific, technical, and quantifiable skills explicitly stated in the resume.
        - Programming languages, analytical methods, technical procedures.
        - Specialized techniques, engineering processes, specific scientific methods.
        - Examples: Python, SQL, Data Analysis, C++, JavaScript, AWS Lambda.

        2. **tools_and_platforms**: Named software, hardware, systems, and digital environments explicitly stated in the resume.
        - Development environments, cloud services, operating systems, databases, specific applications.
        - Examples: Microsoft Azure, Git, Docker, Kubernetes, Jira, Tableau, Salesforce, SAP.

        3. **methodologies_and_frameworks**: Named operational approaches, project management methods, and compliance standards explicitly stated in the resume.
        - Process improvement systems, development practices, quality standards, regulatory frameworks.
        - Examples: Agile, Scrum, Kanban, ITIL, GAAP, GDPR, ISO 27001, Six Sigma.

        4. **domain_knowledge**: Explicitly mentioned industry-specific expertise or specialized knowledge areas in the resume.
        - Business sectors, functional areas, regulatory knowledge, scientific principles.
        - Examples: FinTech, Healthcare Regulations, Supply Chain Management, Quantum Computing, Clinical Trials.
        - **CRITICAL: ONLY extract if explicitly stated in the resume. DO NOT infer or assume.**

        5. **qualifications**: Formal educational credentials, certifications, and licenses, as specific titles, explicitly stated in the resume.
        - Academic degrees, professional certifications, regulatory licenses.
        - Examples: Bachelor's Degree in Computer Science, MBA, PMP, CFA, AWS Certified Solutions Architect, RN License.

        6. **experience_indicators**: Quantified experience mentions and seniority markers found in the resume, including numbers and context.
        - Years of experience, specific project durations, proficiency levels (e.g., "Senior," "Lead").
        - Examples: "5+ years of experience," "3-5 years," "Senior Engineer," "Lead Developer," "Proficiency in."

        === STRICT EXTRACTION METHODOLOGY ===
        1. **EXPLICIT MENTION ONLY**: Extract only terms directly present in the resume. Do not infer, generalize, or semantically expand.
        2. **LITERAL ACCURACY**: Keywords must be extracted as they appear or as direct, commonly recognized atomic components of compound phrases.
        3. **CATEGORY-SPECIFIC**: Ensure extracted terms fit precisely into the defined categories.
        4. **NO INFERENCE**: Do not extract "implied" skills or knowledge unless the skill/knowledge itself is explicitly named.

        === ADVANCED EXTRACTION TECHNIQUES (ADJUSTED FOR STRICT MATCHING) ===

        **Compound Phrase Decomposition:**
        - Break down compound terms into individual, searchable keywords.
        - "Python and SQL development" → ["Python", "SQL"]
        - "Machine Learning and AI systems" → ["Machine Learning", "AI"]
        - "Bachelor's in Computer Science or Engineering" → ["Bachelor's in Computer Science", "Bachelor's in Engineering"]
        - "Microsoft Office Suite" → ["Microsoft Office", "Word", "Excel", "PowerPoint"] (only if components are commonly searched/expected)

        **Contextual Simplification (formerly 'Expansion'):**
        - Include common abbreviations if the full term is also present, or vice-versa, only if both are used or one is a very common, direct substitute.
        - **Strictly limit to direct abbreviations/full terms used within the text or universally understood aliases (e.g., "ML" for "Machine Learning" if ML is used or very common in context).**
        - **DO NOT add speculative or commonly associated tools/platforms not appearing explicitly or strongly implied by the text.**

        **Atomic Term Prioritization:**
        - If a phrase like "experience with relational databases like MySQL and PostgreSQL" appears, extract "MySQL" and "PostgreSQL." "Relational Databases" can also be extracted if it's a specific mention.

        === SUCCESS CRITERIA ===
        - **EXACTNESS**: Keywords must be direct matches to terms or atomic components found in the resume.
        - **COMPREHENSIVE COVERAGE**: Extract every explicit skill, tool, qualification, and competency mentioned.
        - **ATOMIC GRANULARITY**: Break compound phrases into individual, searchable terms suitable for direct string matching.
        - **NO SEMANTIC INFERENCE**: Avoid any keyword not directly supported by the literal text.

        === CRITICAL REMINDERS ===
        - RETURN ONLY THE JSON OBJECT.
        - NO EXPLANATIONS, COMMENTARY, OR METADATA.
        - **EXTRACT ONLY EXPLICITLY STATED COMPETENCIES.**
        - USE EXACT TERMINOLOGY FROM RESUME.
        - ENSURE ALL ARRAYS CONTAIN INDIVIDUAL ATOMIC KEYWORDS.
        - **PRIORITIZE LITERAL PRESENCE OVER SEMANTIC MEANING.**
        - DO NOT HALLUCINATE OR INFER KEYWORDS NOT PRESENT IN THE TEXT.
        - **AVOID EXTRACTING SOFT SKILLS UNLESS EXPLICITLY NAMED (e.g., "Communication Skills," "Leadership"). Do not infer from descriptions like "managed a team."**

    ANALYZE THIS RESUME:
    ---
    {text_input}
    ---
"""


# --- CHANGED: Added keyword weight configuration ---
# --- HIERARCHICAL WEIGHTING CONFIGURATION ---
# This defines the top-level importance of required vs. preferred keywords.
SCORE_COMPOSITION_WEIGHTS = {
    'required': 0.8,
    'preferred': 0.2
}

# This defines the relative importance of categories WITHIN the 'required' group.
# These values should sum to 1.0 (or 100%).
REQUIRED_CATEGORY_WEIGHTS = {
    'hard_skills': 0.2,                   # 20% of the required score
    'tools_and_platforms': 0.6,           # 60% of the required score
    'methodologies_and_frameworks': 0.2   # 20% of the required score
}

# --- NEW: This defines the relative importance of categories WITHIN the 'preferred' group. ---
# These values should also sum to 1.0 (or 100%).
PREFERRED_CATEGORY_WEIGHTS = {
    'hard_skills': 0.1,                   # 10% of the preferred score
    'tools_and_platforms': 0.8,           # 80% of the preferred score
    'methodologies_and_frameworks': 0.1   # 10% of the preferred score
}

# Only these categories will be used for calculating the score
SCORING_CATEGORIES = ['hard_skills', 'tools_and_platforms', 'methodologies_and_frameworks']

# --- NEW FEATURE: User Database Model ---
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    resumes = db.relationship('Resume', backref='owner', lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# --- SQLAlchemy Database Model ---
# DEPLOYMENT: Define the 'resumes' table using a SQLAlchemy Model class.
# This replaces the manual CREATE TABLE SQL query. It's more robust and works with different databases (SQLite, PostgreSQL, etc.).
class Resume(db.Model):
    resume_id = db.Column(db.Integer, primary_key=True)
    file_name = db.Column(db.String(255))
    upload_date = db.Column(db.DateTime, server_default=db.func.now())

    # Contact information
    name = db.Column(db.String(255))
    phone = db.Column(db.String(50))
    email = db.Column(db.String(255))
    linkedin = db.Column(db.String(255))
    location = db.Column(db.String(255))
    github = db.Column(db.String(255))
    website = db.Column(db.String(255))

    # Professional summary
    summary = db.Column(db.Text)
    total_experience_years = db.Column(db.String(50))
    current_title = db.Column(db.String(255))

    # Structured data as JSON
    experiences_json = db.Column(db.Text)
    education_json = db.Column(db.Text)
    certifications_json = db.Column(db.Text)
    skills_json = db.Column(db.Text)
    projects_json = db.Column(db.Text)
    combined_keywords_json = db.Column(db.Text)

    # Flattened text fields for searching
    all_skills_text = db.Column(db.Text)
    all_experience_text = db.Column(db.Text)
    all_education_text = db.Column(db.Text)
    all_certifications_text = db.Column(db.Text)
    all_project_text = db.Column(db.Text)

    # Primary matching field
    searchable_content = db.Column(db.Text)
    
    # Parsing metadata
    parsing_metadata_json = db.Column(db.Text)

    # --- NEW FEATURE: Add columns for user ownership, deduplication, and file storage ---
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content_hash = db.Column(db.String(64), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    __table_args__ = (db.UniqueConstraint('user_id', 'content_hash', name='_user_content_uc'),)
    # ---

# DEPLOYMENT: This creates a command that you can run to initialize the database.
# In your terminal, you would run `flask init-db` one time to create the tables.
# This replaces the `init_database()` function that was called every time the app started.
@app.cli.command('init-db')
def init_db_command():
    """Creates the database tables."""
    db.create_all()
    print('Initialized the database.')

def store_resume_in_db(parsed_resume: dict, user, file_hash: str, file_path: str) -> int:
    """Store parsed resume in the database using SQLAlchemy"""
    # Flattened fields for text search
    all_skills_text = ' | '.join(parsed_resume['skills'])
    all_experience_text = ' ; '.join(
        [' '.join(exp.get('responsibilities', [])) for exp in parsed_resume['experiences']]
        )
    
    all_education_text = ' '.join([
        f"{edu.get('degree', '')} {edu.get('gpa', '')}" 
        for edu in parsed_resume['education']
    ])
    all_certifications_text = ' | '.join(parsed_resume['certifications'])

    all_project_text = ' ; '.join(
        [' '.join(proj.get('details', [])) for proj in parsed_resume.get('projects', [])]
        )

    new_resume = Resume(
        file_name=parsed_resume['file_name'],
        name=parsed_resume['name'],
        phone=parsed_resume['phone'],
        email=parsed_resume['email'],
        linkedin=parsed_resume['linkedin'],
        location=parsed_resume['location'],
        github=parsed_resume['github'],
        website=parsed_resume['website'],
        summary=parsed_resume['summary'],
        total_experience_years=parsed_resume['total_experience_years'],
        current_title=parsed_resume['current_title'],
        experiences_json=json.dumps(parsed_resume['experiences']),
        education_json=json.dumps(parsed_resume['education']),
        certifications_json=json.dumps(parsed_resume['certifications']),
        skills_json=json.dumps(parsed_resume['skills']),
        projects_json=json.dumps(parsed_resume['projects']),
        combined_keywords_json=json.dumps(parsed_resume['combined_keywords']),
        all_skills_text=all_skills_text,
        all_experience_text=all_experience_text,
        all_education_text=all_education_text,
        all_certifications_text=all_certifications_text,
        all_project_text=all_project_text,
        searchable_content=parsed_resume['searchable_content'],
        parsing_metadata_json=json.dumps(parsed_resume['parsing_metadata']),
        # --- NEW FEATURE: Save user and hash info ---
        owner=user,
        content_hash=file_hash,
        file_path=file_path
        # ---
    )
    db.session.add(new_resume)
    db.session.commit()
    return new_resume.resume_id

# --- NEW FEATURE: User Authentication Routes ---
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email address already registered'}), 409
    
    user = User(email=data['email'])
    user.set_password(data['password'])
    db.session.add(user)
    db.session.commit()
    return jsonify({'message': 'User created successfully'}), 201

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(email=data['email']).first()
    if user is None or not user.check_password(data['password']):
        return jsonify({'error': 'Invalid email or password'}), 401
    
    login_user(user)
    return jsonify({'message': 'Logged in successfully', 'user': {'email': user.email}})

@app.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return jsonify({'message': 'Logged out successfully'})

@app.route('/@me')
@login_required
def get_current_user():
    # --- ADD THIS LOGGING ---
    print("--- /@me endpoint HIT ---", flush=True)
    print(f"--- Attempting to access user: {current_user.email} ---", flush=True)
    # ---
    return jsonify({'user': {'email': current_user.email}})

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy', 
        'model_loaded': model is not None,
        'parser_ready': parser is not None
    }), 200

@app.route('/upload_resumes', methods=['POST'])
@login_required
def upload_resumes():
    try:
        if 'files' not in request.files:
            return jsonify({'error': 'No files provided'}), 400
        files = request.files.getlist('files')
        processed_resumes = []
        failed_resumes = []
        skipped_resumes = []
        
        user_upload_folder = os.path.join(app.config['UPLOAD_FOLDER'], f"user_{current_user.id}")
        os.makedirs(user_upload_folder, exist_ok=True)
        logger.info(f"Received {len(files)} file(s) to process.")

        for file in files:
            if file.filename == '':
                continue
            
            logger.info(f"--- Starting processing for {file.filename} ---")
            
            try:
                # STEP 1: Read and Extract Text
                logger.info(f"[{file.filename}] Reading file content.")
                file_content = file.read()
                file.seek(0) # Reset file pointer after reading

                file_hash = hashlib.sha256(file_content).hexdigest()
                
                existing_resume = Resume.query.filter_by(owner=current_user, content_hash=file_hash).first()
                if existing_resume:
                    skipped_resumes.append(file.filename)
                    logger.info(f"Skipping duplicate file {file.filename} for user {current_user.email}")
                    continue

                # Create a unique filename to prevent conflicts
                unique_filename = f"{datetime.utcnow().timestamp()}_{file.filename}"
                file_path = os.path.join(user_upload_folder, unique_filename)
                file.save(file_path)
                
                resume_text = extractor.extract_text(file_content, file.filename)
                if resume_text.startswith('Error:'):
                    raise ValueError(f"Extraction failed: {resume_text}")
                logger.info(f"[{file.filename}] Text extraction successful.")

                # STEP 2: Parse with UniversalResumeParser
                logger.info(f"[{file.filename}] Parsing resume structure.")
                parsed_resume = parser.parse_resume(resume_text, file.filename)
                logger.info(f"[{file.filename}] Parsing successful.")

                # STEP 3: Augment Keywords with Gemini AI
                if not GEMINI_API_KEY:
                    logger.warning(f"[{file.filename}] Gemini API key not found. Using basic skills.")
                    parsed_resume['combined_keywords'] = parsed_resume.get('skills', [])
                else:
                    logger.info(f"[{file.filename}] Calling Gemini API for keyword augmentation.")
                    searchable_text = parsed_resume.get('searchable_content', resume_text)
                    prompt = RESUME_KWD_EXTRACTION_PROMPT.format(text_input=searchable_text)
                    try:
                        model = genai.GenerativeModel('gemini-2.5-flash-lite')
                        generation_config = genai.types.GenerationConfig(response_mime_type="application/json")
                        response = model.generate_content(prompt, generation_config=generation_config)

                        json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
                        if not json_match:
                            raise ValueError("No valid JSON object found in the Gemini response.")
                        
                        json_string = json_match.group(0)
                        ai_keywords_data = json.loads(json_string)
                        
                        flat_keyword_list = []
                        expected_categories = [
                            "hard_skills", "tools_and_platforms", "methodologies_and_frameworks",
                            "domain_knowledge", "qualifications", "experience_indicators"
                        ]
                        for category in expected_categories:
                            keywords = ai_keywords_data.get(category, [])
                            if isinstance(keywords, list):
                                flat_keyword_list.extend(keywords)
                        
                        parsed_resume['combined_keywords'] = flat_keyword_list
                        logger.info(f"[{file.filename}] Gemini call and keyword processing successful.")

                    except Exception as e:
                        logger.error(f"[{file.filename}] Error during Gemini call. Falling back to basic skills. Details: {str(e)}")
                        parsed_resume['combined_keywords'] = parsed_resume.get('skills', [])

                # STEP 4: Store in Database
                logger.info(f"[{file.filename}] Storing parsed data in the database.")
                resume_id = store_resume_in_db(parsed_resume, current_user, file_hash, file_path)
                logger.info(f"[{file.filename}] Successfully stored with resume_id: {resume_id}.")
                
                processed_resumes.append({
                    'resume_id': resume_id, 'name': parsed_resume['name'], 'file_name': file.filename,
                    'skills_count': len(parsed_resume.get('combined_keywords', [])),
                    'experience_years': parsed_resume['total_experience_years'], 'current_title': parsed_resume['current_title']
                })

            except Exception as e:
                # THIS IS THE CRITICAL CHANGE - LOG THE FULL TRACEBACK
                logger.error(f"--- FAILED processing {file.filename}. See full traceback below ---")
                logger.error(traceback.format_exc())
                failed_resumes.append({'filename': file.filename, 'error': f'Processing failed: {str(e)}'})
        
        response = {'message': f'Successfully processed {len(processed_resumes)} resumes', 'processed_resumes': processed_resumes, 'total_processed': len(processed_resumes), 'total_failed': len(failed_resumes)}
        if failed_resumes: response['failed_resumes'] = failed_resumes
        return jsonify(response), 200

    except Exception as e:
        logger.error(f"--- A CRITICAL UNHANDLED ERROR occurred in /upload_resumes ---")
        logger.error(traceback.format_exc())
        return jsonify({'error': 'An unexpected server error occurred.'}), 500
                
@app.route('/extract-keywords', methods=['POST'])
@login_required
def extract_keywords():
    # Check if the Gemini API key was found and configured
    if not GEMINI_API_KEY:
        return jsonify({"error": "Google API key is not configured on the server"}), 500

    data = request.get_json()
    job_description = data.get('job_description', '')
    if not job_description:
        return jsonify({"error": "Job description is required"}), 400

    # This is the prompt we will send to the Gemini model
    prompt = f"""
    CRITICAL: You MUST return ONLY valid JSON. NO explanations, NO additional text, NO markdown formatting.
    === TASK: STRICT KEYWORD EXTRACTION FOR DIRECT MATCHING ===
    Extract ALL **explicitly mentioned** keywords from the job description for direct, exact string matching with resumes. This system prioritizes the literal presence of terms over semantic understanding or inference.

    === REQUIRED JSON OUTPUT FORMAT ===
        {{
        "required_keywords": {{
            "hard_skills": [],
            "tools_and_platforms": [],
            "methodologies_and_frameworks": [],
            "qualifications": [],
            "experience_indicators": []
        }},
        "preferred_keywords": {{
            "hard_skills": [],
            "tools_and_platforms": [],
            "methodologies_and_frameworks": [],
            "qualifications": [],
            "experience_indicators": []
        }}
        }}

        === ESSENTIAL KEYWORD CATEGORIES ===

        1. **hard_skills**: Specific, technical, and quantifiable skills or areas of expertise **explicitly named**.
        - Programming languages, analytical methods, technical procedures.
        - Specialized techniques, engineering processes, specific scientific methods, fields of study.
        - **CRITICAL: ONLY extract skills/expertise. DO NOT extract actions or descriptive qualities. Extract compound skill phrases as they appear.**

        2. **tools_and_platforms**: Named software, hardware, systems, and digital environments **explicitly mentioned**.
        - Development environments, cloud services, operating systems, databases, specific applications, libraries, frameworks (e.g., TensorFlow, PyTorch).
        - Examples: Microsoft Azure, Git, Docker, Kubernetes, Jira, Tableau, Salesforce, SAP, ResNet, GANs, YOLO.

        3. **methodologies_and_frameworks**: Named operational approaches, project management methods, and compliance standards **explicitly mentioned**.
        - Process improvement systems (e.g., Six Sigma), development practices (e.g., Agile, Scrum, Kanban), quality standards, regulatory frameworks (e.g., GDPR, ISO 27001), named architectural patterns (e.g., Microservices).
        - **CRITICAL: Must be a named, formal methodology/framework. DO NOT include broader fields of study (e.g., ML, AI) or general approaches unless they are a defined, formal framework (e.g., Lean Six Sigma).**
        - Examples: Agile, Scrum, Kanban, ITIL, GAAP, GDPR, ISO 27001, Six Sigma.

        4. **qualifications**: Formal educational credentials, certifications, and licenses, as specific titles.
        - Academic degrees, professional certifications, regulatory licenses.
        - Examples: Bachelor's Degree in Computer Science, MBA, PMP, CFA, AWS Certified Solutions Architect, RN License.

        5. **experience_indicators**: Quantified experience requirements and seniority markers, including numbers and context.
        - Years of experience
        - Examples: "5+ years of experience," "3-5 years,"

        === CONTEXTUAL IMPORTANCE CLASSIFICATION ===

        **STRUCTURAL ANALYSIS APPROACH:**
        1. First identify if the job description has explicit sections dividing requirements (e.g., "Requirements vs Preferences," "Must Have vs Nice to Have," "Required vs Preferred").
        2. If explicit sections exist, classify keywords based on their section placement.
        3. If no explicit sections exist, analyze each sentence for contextual classification.

        **REQUIRED CLASSIFICATION INDICATORS:**
        - Proximity to requirement words: "required", "must have", "essential", "mandatory", "need", "shall", "proven experience in".
        - Listed under "Requirements," "Must have," or "Core Competencies" sections.
        - Described as primary responsibilities or critical for the role.
        - **Exclude organizational units, department names, and proper nouns that serve purely as context or collaborators unless explicitly stated as candidate skills, tools, or domain expertise.**

        **PREFERRED CLASSIFICATION INDICATORS:**
        - Near qualifier words: "preferred", "nice to have", "bonus", "plus", "advantage", "ideal", "familiarity with".
        - Listed under "Nice to have," "Additional qualifications," or "Bonus points."
        - Described as "would be great" or "a strong asset."
        - Optional certifications or secondary skills.

        **DEFAULT RULE:** When context is unclear, classify as REQUIRED (this ensures maximum coverage for initial matching).

        === STRICT EXTRACTION METHODOLOGY ===
        1. **EXPLICIT MENTION ONLY**: Extract only terms directly present in the job description. Do not infer, generalize, or semantically expand.
        2. **LITERAL ACCURACY**: Keywords must be extracted as they appear or as direct, commonly recognized atomic components of compound phrases.
        3. **CATEGORY-SPECIFIC**: Ensure extracted terms fit precisely into the defined categories based on their strict definitions.
        4. **NO INFERENCE**: Do not extract "implied" skills or knowledge unless the skill/knowledge itself is explicitly named.

        === ADVANCED EXTRACTION TECHNIQUES (ADJUSTED FOR STRICT MATCHING) ===

        **Compound Phrase Decomposition:**
        - Break down compound terms into individual, searchable keywords.
        - "Python and SQL development" → ["Python", "SQL"]
        - "Machine Learning and AI systems" → ["Machine Learning", "AI"]
        - "Bachelor's in Computer Science or Engineering" → ["Bachelor's in Computer Science", "Bachelor's in Engineering"]
        - "Microsoft Office Suite" → ["Microsoft Office", "Word", "Excel", "PowerPoint"] (only if components are commonly searched/expected)

        **Contextual Simplification (formerly 'Expansion'):**
        - Include common abbreviations if the full term is also present, or vice-versa, only if both are used or one is a very common, direct substitute.
        - **Strictly limit to direct abbreviations/full terms used within the text or universally understood aliases (e.g., "ML" for "Machine Learning" if ML is used or very common in context).**
        - **DO NOT add speculative or commonly associated tools/platforms not explicitly appearing or strongly implied by the text.**

        **Atomic Term Prioritization:**
        - If a phrase like "experience with relational databases like MySQL and PostgreSQL" appears, extract "MySQL" and "PostgreSQL." "Relational Databases" can also be extracted if it's a specific requirement.

        === SUCCESS CRITERIA ===
        - **EXACTNESS**: Keywords must be direct matches to terms or atomic components found in the job description.
        - **COMPREHENSIVE COVERAGE**: Extract every explicit skill, tool, qualification, and competency mentioned.
        - **CONTEXTUAL ACCURACY**: Proper classification based on linguistic cues and section placement.
        - **ATOMIC GRANULARITY**: Break compound phrases into individual, searchable terms suitable for direct string matching.
        - **NO SEMANTIC INFERENCE**: Avoid any keyword not directly supported by the literal text.

        === CRITICAL REMINDERS ===
        - RETURN ONLY THE JSON OBJECT.
        - NO EXPLANATIONS, COMMENTARY, OR METADATA.
        - **EXTRACT ONLY EXPLICITLY STATED COMPETENCIES. DO NOT INFER**
        - USE EXACT TERMINOLOGY FROM JOB DESCRIPTION.
        - ENSURE ALL ARRAYS CONTAIN INDIVIDUAL ATOMIC KEYWORDS.
        - **PRIORITIZE LITERAL PRESENCE OVER SEMANTIC MEANING. DO NOT EXTRACT ACTIONS OR DESCRIPTIVE QUALITIES AS SKILLS.**
        - DO NOT HALLUCINATE OR INFER KEYWORDS NOT PRESENT IN THE TEXT.

    ANALYZE THIS JOB DESCRIPTION:
    ---
    {job_description}
    ---
    """

    try:
        # Initialize the Gemini model
        model = genai.GenerativeModel('gemini-2.5-flash-lite')

        # Set the generation config to ensure the output is JSON
        generation_config = genai.types.GenerationConfig(
            response_mime_type="application/json"
        )

        # Call the API
        response = model.generate_content(prompt, generation_config=generation_config)

        # The response.text will be a clean JSON string
        categorized_keywords = json.loads(response.text)

        return jsonify(categorized_keywords)

    except Exception as e:
        logger.error(f"Error calling Gemini API: {str(e)}")
        return jsonify({"error": "Failed to extract keywords from the Gemini API"}), 500

# --- NEW: Add the feedback report endpoint ---
@app.route('/report-inaccuracy', methods=['POST'])
@login_required
def report_inaccuracy():
    try:
        data = request.get_json()
        if not all(k in data for k in ['job_description', 'resume_file_name', 'report_details']):
            return jsonify({'error': 'Missing required fields for feedback report'}), 400

        recipient_email = os.getenv('MAIL_RECIPIENT')
        if not recipient_email:
            logger.error("MAIL_RECIPIENT environment variable is not set. Cannot send feedback.")
            # Return a success-like message to the user so their experience isn't broken
            return jsonify({'message': 'Feedback received (logging only).'}), 200

        subject = f"Inaccuracy Report for: {data['resume_file_name']}"

        # Format the body of the email for readability
        body = f"""
A user has reported a potential inaccuracy in the matching report.

--- USER ---
Email: {current_user.email}

--- CONTEXT ---
Resume File: {data['resume_file_name']}

==================== JOB DESCRIPTION ====================
{data['job_description']}

==================== GENERATED REPORT DETAILS ====================
{json.dumps(data['report_details'], indent=2)}
        """

        msg = Message(
            subject=subject,
            sender=os.getenv('MAIL_USERNAME'),
            recipients=[recipient_email],
            body=body
        )

        mail.send(msg)

        return jsonify({'message': 'Feedback submitted successfully'}), 201

    except Exception as e:
        logger.error(f"--- ERROR in /report-inaccuracy: {str(e)} ---")
        logger.error(traceback.format_exc())
        return jsonify({'error': 'An internal server error occurred while submitting feedback.'}), 500

@app.route('/match', methods=['POST'])
@login_required
def match_resumes():
    try:
        data = request.json
        # This variable now holds the object with "required_keywords" and "preferred_keywords"
        jd_keywords_categorized = data.get('keywords', {})
        print("--- DEBUG: RECEIVED JD KEYWORDS ---")
        print(json.dumps(jd_keywords_categorized, indent=2))
        print("------------------------------------")
        top_k = min(int(data.get('top_k', 10)), 100)
        resume_ids_to_match = data.get('resume_ids')

        if not jd_keywords_categorized:
            return jsonify({'error': 'No keywords provided for matching'}), 400

        # --- STEP 1: Calculate max possible counts for each category ---
        max_counts = {
            'required': {cat: 0 for cat in SCORING_CATEGORIES},
            'preferred': {cat: 0 for cat in SCORING_CATEGORIES}
        }

        for importance in ['required', 'preferred']:
            for category in SCORING_CATEGORIES:
                count = len(jd_keywords_categorized.get(f'{importance}_keywords', {}).get(category, ))
                max_counts[importance][category] = count

        # --- STEP 2: Dynamically adjust weights based on available keywords ---
        # Adjust top-level (required vs preferred) weights
        final_composition_weights = SCORE_COMPOSITION_WEIGHTS.copy()
        has_required = any(max_counts['required'].values())
        has_preferred = any(max_counts['preferred'].values())

        if has_required and not has_preferred:
            final_composition_weights['required'] = 1.0
            final_composition_weights['preferred'] = 0.0
        elif not has_required and has_preferred:
            final_composition_weights['required'] = 0.0
            final_composition_weights['preferred'] = 1.0
        elif not has_required and not has_preferred:
            return jsonify({'results': [], 'message': 'No scorable keywords found in the job description.'})

        # Adjust nested weights for the 'required' category
        final_required_weights = {}
        required_weight_present = 0
        for category, weight in REQUIRED_CATEGORY_WEIGHTS.items():
            if max_counts['required'][category] > 0:
                final_required_weights[category] = weight
                required_weight_present += weight
        
        if required_weight_present > 0:
            for category in final_required_weights:
                final_required_weights[category] /= required_weight_present

        # --- NEW: Adjust nested weights for the 'preferred' category ---
        final_preferred_weights = {}
        preferred_weight_present = 0
        for category, weight in PREFERRED_CATEGORY_WEIGHTS.items():
            if max_counts['preferred'][category] > 0:
                final_preferred_weights[category] = weight
                preferred_weight_present += weight
        
        if preferred_weight_present > 0:
            for category in final_preferred_weights:
                final_preferred_weights[category] /= preferred_weight_present

        # --- STEP 3: Score resumes ---
        # Build query based on whether specific resumes were selected
        base_query = Resume.query.filter_by(owner=current_user)
        if resume_ids_to_match and isinstance(resume_ids_to_match, list):
            base_query = base_query.filter(Resume.resume_id.in_(resume_ids_to_match))
        
        resumes_to_score = base_query.all()
        scored_resumes = []

        print(f"--- DEBUG: SCORING {len(resumes_to_score)} RESUMES ---")

        for i, resume in enumerate(resumes_to_score):
            # The resume keywords are a simple, flat list, which is correct
            resume_keywords = set(k.lower() for k in json.loads(resume.combined_keywords_json)) if resume.combined_keywords_json else set()
            if i == 0:
                print(f"--- DEBUG: KEYWORDS FOR FIRST RESUME ({resume.file_name}) ---")
                print(resume_keywords)
                print("-------------------------------------------------")

            current_matches = {
                'required': {cat: 0 for cat in SCORING_CATEGORIES},
                'preferred': {cat: 0 for cat in SCORING_CATEGORIES}
            }
            report_details = {"scoring_keywords": {}, "additional_keywords": {}}
            
            # Iterate through the nested JD keywords to compare against the flat resume keyword list
            for importance, categories in jd_keywords_categorized.items():
                importance_key = importance.replace('_keywords', '')
                for category, keywords in categories.items():
                    is_scoring_cat = category in SCORING_CATEGORIES
                    report_target = report_details["scoring_keywords"] if is_scoring_cat else report_details["additional_keywords"]
                    
                    if category not in report_target:
                        report_target[category] = {'matched': [], 'missing': []}

                    for kw in keywords:
                        if kw.lower() in resume_keywords:
                            report_target[category]['matched'].append(kw)
                            if is_scoring_cat and importance_key in current_matches and category in current_matches[importance_key]:
                                current_matches[importance_key][category] += 1
                        else:
                            report_target[category]['missing'].append(kw)
            
            # --- STEP 4: Calculate final hierarchical score ---
            # Calculate the composite required score
            required_score_component = 0
            if has_required:
                for category, weight in final_required_weights.items():
                    match_count = current_matches['required'][category]
                    max_count = max_counts['required'][category]
                    category_match_pct = (match_count / max_count) if max_count > 0 else 0
                    required_score_component += category_match_pct * weight

            # --- CHANGED: Calculate the composite preferred score using its own weights ---
            preferred_score_component = 0
            if has_preferred:
                for category, weight in final_preferred_weights.items():
                    match_count = current_matches['preferred'][category]
                    max_count = max_counts['preferred'][category]
                    category_match_pct = (match_count / max_count) if max_count > 0 else 0
                    preferred_score_component += category_match_pct * weight

            # Combine for the final score
            final_score = (required_score_component * final_composition_weights['required']) + \
                          (preferred_score_component * final_composition_weights['preferred'])
            
            # --- NEW FEATURE: Add a direct download URL to the result ---
            file_url = f"/download/resume/{resume.resume_id}"
            # ---
            scored_resumes.append({
                "resume_id": resume.resume_id, "name": resume.name, "score": final_score, "current_title": resume.current_title,
                "summary": (resume.summary[:250] + "...") if resume.summary and len(resume.summary) > 250 else resume.summary,
                "file_name": resume.file_name, "report_details": report_details,
                "file_url": file_url
            })
            
        sorted_resumes = sorted(scored_resumes, key=lambda x: x['score'], reverse=True)
        return jsonify({"results": sorted_resumes[:top_k], "total_resumes_scored": len(resumes_to_score)}), 200

    except Exception as e:
        logger.error(f"Error in matching: {e}")
        return jsonify({'error': f'Failed to match: {str(e)}'}), 500

# --- NEW FEATURE: Route to list a user's resumes ---
@app.route('/resumes', methods=['GET'])
@login_required
def get_user_resumes():
    resumes = Resume.query.filter_by(owner=current_user).order_by(Resume.upload_date.desc()).all()
    resumes_list = [
        {
            "resume_id": r.resume_id,
            "file_name": r.file_name,
            "candidate_name": r.name,
            "upload_date": r.upload_date.isoformat()
        } for r in resumes
    ]
    return jsonify(resumes_list)

# --- NEW FEATURE: Route to download a specific resume file ---
@app.route('/download/resume/<int:resume_id>', methods=['GET'])
@login_required
def download_resume(resume_id):
    resume = Resume.query.get_or_404(resume_id)
    if resume.owner != current_user:
        return jsonify({'error': 'Forbidden'}), 403
    
    # Use send_from_directory for security
    directory = os.path.dirname(resume.file_path)
    filename = os.path.basename(resume.file_path)
    return send_from_directory(directory, filename, as_attachment=True)
# ---

@app.route('/resume/<int:resume_id>', methods=['GET'])
@login_required
def get_resume_details(resume_id):
    try:
        # DEPLOYMENT: Fetch a single resume by its ID using a standard SQLAlchemy method.
        # This is safer and easier than writing a manual SQL query.
        resume = Resume.query.get_or_404(resume_id)
        
        # This check ensures a user cannot access another user's resume details by guessing the ID.
        if resume.owner != current_user:
            return jsonify({"error": "You do not have permission to view this resume."}), 403

        # DEPLOYMENT: Convert the SQLAlchemy object to a dictionary for the JSON response.
        resume_dict = {c.name: getattr(resume, c.name) for c in resume.__table__.columns}
        
        json_fields = ['experiences_json', 'education_json', 'certifications_json', 'skills_json', 'projects_json']
        for field in json_fields:
            if resume_dict.get(field):
                try:
                    resume_dict[field] = json.loads(resume_dict[field])
                except:
                    resume_dict[field] = [] # Default to empty list on parsing error
        return jsonify(resume_dict), 200
    except Exception as e:
        logger.error(f"Error getting resume details: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/stats', methods=['GET'])
@login_required
def get_stats():
    try:
        # DEPLOYMENT: Use SQLAlchemy to perform calculations.
        total_resumes = db.session.query(db.func.count(Resume.resume_id)).filter(Resume.owner == current_user).scalar()
        exp_years_text = db.session.query(Resume.total_experience_years).filter(Resume.owner == current_user).all()
        
        total_exp = 0
        valid_entries = 0
        for (text,) in exp_years_text:
            if text:
                match = re.search(r'\d+\.?\d*', text)
                if match:
                    total_exp += float(match.group())
                    valid_entries += 1
        
        avg_experience = (total_exp / valid_entries) if valid_entries > 0 else 0.0

        return jsonify({
            'total_resumes_loaded': total_resumes,
            'average_experience_years': round(avg_experience, 1),
            'parser_ready': True,
            'database_ready': True
        }), 200
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({'error': str(e)}), 500

"""@app.route('/debug/database', methods=['GET'])
def debug_database():
    try:
        conn = sqlite3.connect('resumes.db')
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM resumes')
        total_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM resumes WHERE searchable_content IS NOT NULL AND searchable_content != ""')
        valid_content_count = cursor.fetchone()[0]
        cursor.execute('SELECT resume_id, name, file_name, LENGTH(searchable_content) as content_length, parsing_metadata_json FROM resumes LIMIT 10')
        sample_resumes = cursor.fetchall()
        cursor.execute('SELECT * FROM resumes LIMIT 1')
        columns = [description[0] for description in cursor.description]
        full_resume = cursor.fetchone()
        conn.close()
        result = {
            'total_resumes': total_count,
            'resumes_with_searchable_content': valid_content_count,
            'sample_resumes': [
                {
                    'id': r[0],
                    'name': r[1] or 'No name',
                    'file_name': r[2],
                    'searchable_content_length': r[3] or 0,
                    'parsing_metadata': r[4]
                } for r in sample_resumes
            ],
            'database_columns': columns,
            'first_resume_data': dict(zip(columns, full_resume)) if full_resume else None
        }
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Debug database error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/debug/clear_database', methods=['POST'])
def clear_database():
    try:
        conn = sqlite3.connect('resumes.db')
        cursor = conn.cursor()
        cursor.execute('DELETE FROM resumes')
        conn.commit()
        conn.close()
        return jsonify({'message': 'Database cleared successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
"""

# --- ADD THIS ENTIRE BLOCK FOR DIAGNOSTIC PURPOSES ---
@app.route('/test-cors', methods=['GET'])
def test_cors_route():
    """A simple route to definitively test if CORS preflight is working."""
    logger.info("CORS test route was successfully accessed.")
    return jsonify({"message": "CORS test successful!"})

# This will catch any unhandled exception in your application
# and log it with a full traceback. This is CRUCIAL for debugging.
@app.errorhandler(Exception)
def handle_exception(e):
    # Log the full traceback
    import traceback
    traceback.print_exc()
    # Return a JSON response
    return jsonify({
        "error": "An internal server error occurred.",
        "message": str(e)
    }), 500
# ---

"""if __name__ == '__main__':
    print("Starting Job Matching API with Universal Resume Parser...")
    print("Endpoints available:")
    print("  POST /upload_resumes - Upload PDF/DOCX files")
    print("  POST /match - Match job description with resumes")
    print("  GET /resume/<id> - Get detailed resume information")
    print("  GET /stats - Get system statistics")
    print("  GET /health - Health check")
    app.run(host='0.0.0.0', port=5000)
"""