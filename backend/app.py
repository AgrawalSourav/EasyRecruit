from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv  # Import the load_dotenv function
from sentence_transformers import SentenceTransformer
import json
import sqlite3
from datetime import datetime
from rank_bm25 import BM25Okapi
import logging
import re
import os
import asyncio
# Import our custom modules
from resume_parser import UniversalResumeParser
from pdf_extractor import DocumentExtractor
import google.generativeai as genai

# Configure the Gemini client with the API key from your environment variables
GEMINI_API_KEY = os.environ.get("GOOGLE_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# DEPLOYMENT: Load environment variables from a .env file. This is crucial for managing secret keys like the database URL.
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# --- Database Configuration ---
# DEPLOYMENT: Configure SQLAlchemy to connect to the database.
# It reads the database URL from an environment variable ('DATABASE_URL').
# If it's not found, it defaults to a local SQLite file named 'resumes_dev.db' for development.
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL", "sqlite:///resumes_dev.db")
# DEPLOYMENT: Disable a SQLAlchemy feature that adds overhead, which is not needed here.
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# DEPLOYMENT: Initialize the SQLAlchemy object, which we will use for all database operations.
db = SQLAlchemy(app)

print("Loading sentence transformer model...")
model = SentenceTransformer('all-mpnet-base-v2')
parser = UniversalResumeParser()
extractor = DocumentExtractor()
print("All components loaded successfully!")

# --- CHANGED: Added keyword weight configuration ---
# You can easily adjust the importance of different skill categories here.
KEYWORD_WEIGHTS = {
    'required': {
        'hard_skills': 10,
        'tools_and_platforms': 8,
        'methodologies_and_frameworks': 7,
        'default': 5 
    },
    'preferred': {
        'hard_skills': 4,
        'tools_and_platforms': 3,
        'methodologies_and_frameworks': 2,
        'default': 1
    }
}
# Only these categories will be used for calculating the score
SCORING_CATEGORIES = ['hard_skills', 'tools_and_platforms', 'methodologies_and_frameworks']

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

# DEPLOYMENT: This creates a command that you can run to initialize the database.
# In your terminal, you would run `flask init-db` one time to create the tables.
# This replaces the `init_database()` function that was called every time the app started.
@app.cli.command('init-db')
def init_db_command():
    """Creates the database tables."""
    db.create_all()
    print('Initialized the database.')

def store_resume_in_db(parsed_resume: dict) -> int:
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
        parsing_metadata_json=json.dumps(parsed_resume['parsing_metadata'])
    )
    db.session.add(new_resume)
    db.session.commit()
    return new_resume.resume_id

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy', 
        'model_loaded': model is not None,
        'parser_ready': parser is not None
    }), 200

@app.route('/upload_resumes', methods=['POST'])
def upload_resumes():
    try:
        if 'files' not in request.files:
            return jsonify({'error': 'No files provided'}), 400
        files = request.files.getlist('files')
        processed_resumes = []
        failed_resumes = []
        for file in files:
            if file.filename == '':
                continue
            try:
                file_content = file.read()
                resume_text = extractor.extract_text(file_content, file.filename)
                if resume_text.startswith('Error:'):
                    failed_resumes.append({
                        'filename': file.filename,
                        'error': resume_text
                    })
                    continue
                parsed_resume = parser.parse_resume(resume_text, file.filename)
                # Run async augment_keywords synchronously with asyncio.run
                parsed_augmented = asyncio.run(parser.augment_keywords(parsed_resume))

                resume_id = store_resume_in_db(parsed_augmented)
                processed_resumes.append({
                    'resume_id': resume_id,
                    'name': parsed_resume['name'],
                    'file_name': file.filename,
                    'skills_count': len(parsed_augmented.get('combined_keywords', [])),
                    'experience_years': parsed_resume['total_experience_years'],
                    'current_title': parsed_resume['current_title']
                })
            except Exception as e:
                logger.error(f"Error processing {file.filename}: {str(e)}")
                failed_resumes.append({
                    'filename': file.filename,
                    'error': f'Processing failed: {str(e)}'
                })
        response = {
            'message': f'Successfully processed {len(processed_resumes)} resumes',
            'processed_resumes': processed_resumes,
            'total_processed': len(processed_resumes),
            'total_failed': len(failed_resumes)
        }
        if failed_resumes:
            response['failed_resumes'] = failed_resumes
        return jsonify(response), 200
    except Exception as e:
        logger.error(f"Error in upload_resumes: {str(e)}")
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

@app.route('/extract-keywords', methods=['POST'])
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
    === TASK: RESEARCH-VALIDATED KEYWORD EXTRACTION ===
    Extract ALL essential keywords from job descriptions using academic research-validated methodologies for optimal ATS and semantic matching. This system implements findings from NLP research papers and commercial platforms for production-level resume matching.

    === REQUIRED JSON OUTPUT FORMAT ===
            {
            "required_keywords": {
                "hard_skills": [],
                "tools_and_platforms": [],
                "methodologies_and_frameworks": [],
                "domain_knowledge": [],
                "qualifications": [],
                "experience_indicators": []
            },
            "preferred_keywords": {
                "hard_skills": [],
                "tools_and_platforms": [],
                "methodologies_and_frameworks": [],
                "domain_knowledge": [],
                "qualifications": [],
                "experience_indicators": []
            }
            }

            === ESSENTIAL KEYWORD CATEGORIES (Research-Validated) ===

            1. **hard_skills**: Quantifiable, task-oriented technical competencies essential for role performance
            - Programming languages, analytical methods, technical procedures
            - Specialized techniques, laboratory methods, engineering processes
            - Measurable competencies with clear learning pathways
            - Examples: Python, Statistical Analysis, PCR, Finite Element Analysis, Machine Learning

            2. **tools_and_platforms**: Specific software, hardware, and digital platforms
            - Development environments, cloud services, collaboration tools
            - Industry-specific software, machinery, laboratory equipment
            - Examples: AWS, Git, Salesforce, Docker, Jira, Adobe Creative Suite

            3. **methodologies_and_frameworks**: Named operational and project management approaches
            - Process improvement systems, development practices, quality standards
            - Compliance frameworks, industry methodologies
            - Examples: Agile, Scrum, Lean Six Sigma, DevOps, ISO 27001, GDPR

            4. **domain_knowledge**: Industry-specific expertise and specialized knowledge areas ONLY if explicitly mentioned
            - Business sectors, functional areas, regulatory knowledge
            - Theoretical concepts, business frameworks, scientific principles
            - Examples: Healthcare, FinTech, GAAP, Quantum Mechanics, Supply Chain
            - **CRITICAL: Only extract if explicitly stated in the job description. Do not infer or assume.**

            5. **qualifications**: Formal educational credentials, certifications, and licenses
            - Academic degrees, professional certifications, regulatory licenses
            - Must be specific titles, not general categories
            - Examples: Bachelor of Science, PMP, CPA, AWS Solutions Architect, Registered Nurse

            6. **experience_indicators**: Quantified experience requirements and seniority markers
            - Years of experience, proficiency levels, leadership scope
            - Extract both numbers and context

            === CONTEXTUAL IMPORTANCE CLASSIFICATION ===

            **STRUCTURAL ANALYSIS APPROACH:**
            1. First identify if the job description has explicit sections dividing requirements (e.g., "Requirements vs Preferences," "Must Have vs Nice to Have," "Required vs Preferred").
            2. If explicit sections exist, classify keywords based on their section placement.
            3. If no explicit sections exist, analyze each sentence for contextual classification.

            **REQUIRED CLASSIFICATION INDICATORS:**
            - Proximity to requirement words: "required", "must", "essential", "mandatory", "need", "shall"
            - Listed under "Requirements" or "Must have" sections
            - Described as core responsibilities or primary duties
            - **Ignore or exclude organizational units, department names, and proper nouns that serve purely as context or collaborators, unless explicitly mentioned as candidate skills or domain expertise.**

            **PREFERRED CLASSIFICATION INDICATORS:**
            - Near qualifier words: "preferred", "nice to have", "bonus", "plus", "advantage", "ideal"
            - Listed under "Nice to have" or "Additional qualifications"
            - Described as "would be great" or "a plus"
            - Optional certifications or secondary skills

            **DEFAULT RULE:** When context is unclear, classify as REQUIRED (research shows this improves matching accuracy)

            === RESEARCH-BASED EXTRACTION METHODOLOGY ===
            1. SEMANTIC SIGNIFICANCE: Prioritize contextual meaning over frequency - extract keywords based on professional relevance and semantic centrality within the text
            2. HIERARCHICAL CLASSIFICATION: Use established skill taxonomies (ESCO, O*NET principles) to classify and validate keyword importance
            3. CONTEXTUAL IMPORTANCE RANKING: Analyze proximity to requirement indicators, repetition patterns, and hierarchical positioning
            4. DOMAIN-SPECIFIC RELEVANCE: Extract keywords that carry specialized meaning within professional contexts
            5. COMPREHENSIVE COVERAGE: Capture both explicit mentions and implied competencies from job responsibilities

            === ADVANCED EXTRACTION TECHNIQUES ===

            **Semantic Role Analysis:**
            - Extract implied skills from job responsibilities ("manage team" → Leadership, Team Management)
            - Capture domain expertise from industry context ONLY if explicitly mentioned
            - **When extracting from action phrases involving interactions with entities or teams, prioritize extracting the implied behavioral or soft skill instead of the named entity or organizational unit.**
            - **Filter out named entities, department names, or organization titles unless they directly represent candidate-required domain expertise or qualifications.**
            - **Limit extraction of implied tools and platforms to only those explicitly mentioned or clearly indicated in context. Do not infer specific software or platforms solely from generic terms unless directly named.**

            **Compound Phrase Decomposition:**
            - "Python and SQL development" → ["Python", "SQL", "Software Development"]  
            - "Machine learning and AI systems" → ["Machine Learning", "AI", "Artificial Intelligence", "AI Systems"]
            - "Bachelor's in Computer Science or Engineering" → ["Bachelor's Degree in Computer Science", "Bachelor's degree in Engineering"]

            **Contextual Expansion:**
            - Include both full terms and common abbreviations
            - Extract synonyms mentioned in context
            - Capture implied competencies from complex phrases
            - **Restrict expansion to avoid adding speculative or commonly associated tools/platforms not appearing explicitly or strongly implied by the text.**

            **Industry-Specific Extraction:**
            - Prioritize domain-relevant terminology
            - Extract compliance and regulatory terms specific to sector ONLY if explicitly mentioned
            - Identify industry-standard tools and methodologies ONLY if explicitly mentioned

            === RESEARCH-VALIDATED SUCCESS CRITERIA ===
            - SEMANTIC PRECISION: Keywords must carry professional significance, not just statistical frequency
            - COMPREHENSIVE COVERAGE: Extract every skill, tool, qualification, and competency mentioned or implied
            - CONTEXTUAL ACCURACY: Proper classification based on linguistic cues and placement
            - ATOMIC GRANULARITY: Break compound phrases into individual, searchable terms
            - DOMAIN RELEVANCE: Prioritize industry-specific and role-relevant terminology
            - PRODUCTION QUALITY: Suitable for commercial ATS and semantic matching systems

            === CRITICAL REMINDERS ===
            - RETURN ONLY THE JSON OBJECT
            - NO EXPLANATIONS, COMMENTARY, OR METADATA
            - EXTRACT BOTH EXPLICIT AND IMPLIED COMPETENCIES
            - USE EXACT TERMINOLOGY FROM JOB DESCRIPTION WHEN POSSIBLE
            - ENSURE ALL ARRAYS CONTAIN INDIVIDUAL ATOMIC KEYWORDS
            - PRIORITIZE SEMANTIC MEANING OVER WORD FREQUENCY
            - DO NOT HALLUCINATE OR INFER KEYWORDS NOT PRESENT IN THE TEXT

            ANALYZE THIS JOB DESCRIPTION:

    Job Description:
    ---
    {job_description}
    ---
    """

    try:
        # Initialize the Gemini model
        model = genai.GenerativeModel('gemini-1.0-pro')

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


@app.route('/match', methods=['POST'])
def match_resumes():
    try:
        data = request.json
        jd_keywords_categorized = data.get('keywords', {})
        top_k = min(int(data.get('top_k', 10)), 100)

        if not jd_keywords_categorized:
            return jsonify({'error': 'No keywords provided for matching'}), 400

        # 1. Calculate max score using ONLY scoring categories
        max_possible_score = 0
        for importance, categories in jd_keywords_categorized.items():
            for category, keywords in categories.items():
                if category in SCORING_CATEGORIES: # <-- The key change is here
                    weight = KEYWORD_WEIGHTS.get(importance, {}).get(category, 1)
                    max_possible_score += len(keywords) * weight

        if max_possible_score == 0:
            return jsonify({'results': [], 'message': 'No relevant keywords to score against in the provided job description.'})

        # 2. DEPLOYMENT: Fetch all resumes using the SQLAlchemy ORM. This replaces the raw sqlite3 query.
        all_resumes = Resume.query.all()

        # 3. Score each resume and build the detailed report
        scored_resumes = []
        for resume in all_resumes:
            resume_keywords = set(k.lower() for k in json.loads(resume.combined_keywords_json)) if resume.combined_keywords_json else set()
            
            current_score = 0
            report_details = {"scoring_keywords": {}, "additional_keywords": {}}

            for importance, categories in jd_keywords_categorized.items():
                for category, keywords in categories.items():
                    is_scoring_cat = category in SCORING_CATEGORIES
                    report_target = report_details["scoring_keywords"] if is_scoring_cat else report_details["additional_keywords"]
                    
                    if category not in report_target:
                        report_target[category] = {'matched': [], 'missing': []}

                    weight = KEYWORD_WEIGHTS.get(importance, {}).get(category, 1)

                    for kw in keywords:
                        if kw.lower() in resume_keywords:
                            report_target[category]['matched'].append(kw)
                            if is_scoring_cat:
                                current_score += weight
                        else:
                            report_target[category]['missing'].append(kw)
            
            normalized_score = (current_score / max_possible_score) if max_possible_score > 0 else 0
            
            scored_resumes.append({
                "resume_id": resume.resume_id,
                "name": resume.name,
                "score": normalized_score,
                "current_title": resume.current_title,
                "summary": (resume.summary[:250] + "...") if resume.summary and len(resume.summary) > 250 else resume.summary,
                "file_name": resume.file_name,
                "report_details": report_details
            })
        
        # 4. Sort and return results
        sorted_resumes = sorted(scored_resumes, key=lambda x: x['score'], reverse=True)
        top_results = sorted_resumes[:top_k]

        return jsonify({"results": top_results, "total_resumes_scored": len(all_resumes)}), 200

    except Exception as e:
        logger.error(f"Error in matching: {e}")
        return jsonify({'error': f'Failed to match: {str(e)}'}), 500

@app.route('/resume/<int:resume_id>', methods=['GET'])
def get_resume_details(resume_id):
    try:
        # DEPLOYMENT: Fetch a single resume by its ID using a standard SQLAlchemy method.
        # This is safer and easier than writing a manual SQL query.
        resume = Resume.query.get_or_404(resume_id)
        
        # DEPLOYMENT: Convert the SQLAlchemy object to a dictionary for the JSON response.
        resume_dict = {c.name: getattr(resume, c.name) for c in resume.__table__.columns}
        
        json_fields = ['experiences_json', 'education_json', 'certifications_json', 'skills_json', 'parsing_metadata_json']
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
def get_stats():
    try:
        # DEPLOYMENT: Use SQLAlchemy to perform calculations.
        total_resumes = db.session.query(db.func.count(Resume.resume_id)).scalar()
        exp_years_text = db.session.query(Resume.total_experience_years).all()
        
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
if __name__ == '__main__':
    print("Starting Job Matching API with Universal Resume Parser...")
    print("Endpoints available:")
    print("  POST /upload_resumes - Upload PDF/DOCX files")
    print("  POST /match - Match job description with resumes")
    print("  GET /resume/<id> - Get detailed resume information")
    print("  GET /stats - Get system statistics")
    print("  GET /health - Health check")
    app.run(host='0.0.0.0', port=5000)
