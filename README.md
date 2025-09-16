# AI-Powered Resume Screening Platform
An intelligent, cloud-native web application for securely uploading, screening, and matching candidate resumes to job descriptions using Google's Gemini Generative AI.

Live Application Link (Replace with your final Netlify URL)

## Core Features
1. **Secure User Authentication**: Full registration and login system. Each user has their own private and secure resume database.
2. **Multi-Format Resume Upload**: Natively parses .pdf, .docx, and .txt files, extracting content automatically.
3. **Persistent & Secure File Storage**: User-uploaded resumes are stored on a persistent cloud disk, ensuring they are safe and available across deployments and server restarts.
4. **AI-Powered Job Description Analysis**: Leverages Google's Gemini AI to perform deep analysis on job descriptions, extracting a detailed taxonomy of skills, tools, platforms, and qualifications.
5. **Advanced Candidate Matching**: Scores and ranks a user-selected pool of candidates against the AI-extracted keywords from a job description.
6. **Detailed Match Reports**: Generates interactive reports for each candidate, showing a clear breakdown of matched and missing skills.
7. **Cloud-Native & Scalable**: Deployed on a modern, professional stack with a clear separation between the frontend (Netlify) and backend (Render) for optimal performance and scalability.

## Application Workflow
The user experience is designed as a clear, step-by-step process:
1. **Register & Login**: Create a secure account or log in to access your dashboard.
2. **Upload Resumes (`Resume` Tab)**: Build your candidate pool by uploading one or more resumes. The system processes them and stores them securely.
3. **Analyze a Job (`Job Description` Tab)**: Paste a job description and click "Extract Keywords." The AI analyzes the text and prepares it for matching.
4. **Find Top Candidates (`Matches` Tab)**:
   - Select which of your uploaded resumes you want to screen for the role.
   - Click the "Find Top Matches" button to run the analysis.
   - Review the ranked list of candidates, view detailed keyword match reports, and download the original resume files.

## Technical Architecture
This project was built with a modern, production-ready technology stack.

| Component	      | Technology/Service       | Purpose
| :---            | :---                     | :---
| **Frontend** |	React, React Bootstrap, Framer Motion | Dynamic and responsive user interface.
| **Backend** | Flask (Python) | Core API logic and request handling.
| **AI Model** | Google Gemini 1.5 Flash | Job description analysis and keyword extraction.
| **Production Server** | Gunicorn | Production-grade WSGI server for the Flask app.
| **Database** | PostgreSQL | Relational database for storing user and resume metadata.
| **ORM & Migrations** | SQLAlchemy, Flask-Migrate | Database interaction and schema management.
| **Authentication** | Flask-Login | Secure, session-based user authentication.
| **Frontend Deployment** | Netlify | Continuous deployment and hosting for the React app.
| **Backend/DB Deployment** | Render | PaaS for hosting the Flask API and PostgreSQL database.
| **Persistent File Storage** | Render Disks | Permanent storage for uploaded resume files.

## Future Enhancements
- **Integrate with ATS**: Connect to third-party Applicant Tracking Systems like Greenhouse or Lever to pull candidate data.
- **Batch Matching**: Allow users to match their entire resume pool against multiple jobs at once.
- **Dedicated Task Queue**: Implement Celery and Redis for handling long-running resume parsing and AI analysis jobs in the background.
- **Analytics Dashboard**: Create a dashboard showing analytics on the skills present in the candidate pool.
- **Advanced Filtering**: Add options to filter matches by years of experience, location, etc.