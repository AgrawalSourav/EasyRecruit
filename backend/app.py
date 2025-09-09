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
    data = request.get_json()
    job_description = data.get('job_description', '')
    if not job_description:
        return jsonify({"error": "Job description is required"}), 400
    
    # Call the new method we just created
    categorized_keywords = asyncio.run(parser.extract_keywords_ollama(job_description))
    
    if not categorized_keywords:
        return jsonify({"error": "Failed to extract keywords from the model"}), 500
        
    return jsonify(categorized_keywords)

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
