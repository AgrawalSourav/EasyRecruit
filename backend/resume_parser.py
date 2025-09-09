import re
import json
from typing import Dict, List, Any, Tuple
from datetime import datetime
import logging
from dateutil import parser as date_parser
import asyncio
from ollama import AsyncClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class UniversalResumeParser:
    def __init__(self):
        self.experience_keywords = [
            'experience', 'employment', 'work history', 'professional experience',
            'career history', 'work experience', 'professional background',
            'employment history', 'recent experience', 'relevant experience'
        ]
        self.education_keywords = [
            'education', 'academic background', 'academic qualifications',
            'educational background', 'academic history', 'qualifications',
            'degrees', 'academic credentials'
        ]
        self.skills_keywords = [
            'skills', 'technical skills', 'core competencies', 'competencies',
            'technical competencies', 'key skills', 'expertise', 'proficiencies',
            'technologies', 'technical proficiencies', 'core skills',
            'technical expertise', 'skill set'
        ]
        self.certification_keywords = [
            'certifications', 'certificates', 'professional certifications',
            'licenses', 'credentials', 'professional credentials',
            'professional licenses', 'industry certifications'
        ]
        self.projects_keywords = [
            'projects', 'project', 'personal projects', 'professional projects', 'key projects', 'selected projects',
            'academic projects'
            ]

        self.summary_keywords = [
            'summary', 'objective', 'profile', 'about', 'professional summary', 'career summary'
            ]

        self.job_title_indicators = [
            'manager', 'director', 'engineer', 'developer', 'analyst', 'specialist',
            'coordinator', 'supervisor', 'lead', 'senior', 'junior', 'associate',
            'consultant', 'architect', 'administrator', 'officer', 'executive',
            'designer', 'researcher', 'scientist', 'technician', 'representative'
        ]
        # For skills detection
        self.technical_skill_categories = {
            'programming_languages': [
                'python', 'java', 'javascript', 'c++', 'c#', 'php', 'ruby', 'go',
                'rust', 'swift', 'kotlin', 'scala', 'r', 'matlab', 'sql', 'html',
                'css', 'typescript', 'perl', 'shell', 'bash', 'powershell'
            ],
            'databases': [
                'mysql', 'postgresql', 'mongodb', 'redis', 'cassandra', 'oracle',
                'sql server', 'sqlite', 'elasticsearch', 'neo4j', 'dynamodb',
                'firebase', 'mariadb', 'influxdb'
            ],
            'frameworks': [
                'react', 'angular', 'vue', 'django', 'flask', 'spring', 'express',
                'nodejs', 'laravel', 'rails', '.net', 'asp.net', 'jquery',
                'bootstrap', 'tensorflow', 'pytorch', 'keras'
            ],
            'cloud_platforms': [
                'aws', 'azure', 'gcp', 'google cloud', 'kubernetes', 'docker',
                'terraform', 'jenkins', 'gitlab', 'github', 'bitbucket',
                'heroku', 'digitalocean', 'cloudflare'
            ],
            'analytics_tools': [
                'tableau', 'powerbi', 'qlik', 'looker', 'excel', 'google analytics',
                'mixpanel', 'amplitude', 'sas', 'spss', 'r studio', 'jupyter',
                'pandas', 'numpy', 'matplotlib', 'seaborn'
            ],
            'ai_ml_tools': [
                'tensorflow', 'pytorch', 'scikit-learn', 'keras', 'pandas', 'numpy',
                'opencv', 'nlp', 'openai', 'huggingface', 'spark', 'hadoop',
                'mlflow', 'airflow', 'databricks'
            ]
        }

    def clean_text(self, text: str) -> str:
        if not text:
            return ""
        text = re.sub(r'\s+', ' ', text.strip())
        text = re.sub(r'^[•·▪▫◦‣⁃]\s*', '', text)
        text = re.sub(r'[^\x00-\x7F]+', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def extract_contact_info(self, text: str) -> Dict[str, str]:
        contact_info = {
            'name': '',   # skip extracting here
            'phone': '',
            'email': '',
            'linkedin': '',
            'location': '',  # skip extracting here
            'github': '',
            'website': ''
        }
        # Extract email
        m = re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", text)
        if m:
            contact_info['email'] = m.group()

        # Extract phone    
        phone_patterns = [
            r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}",  
            r"\+\d{1,3}[-.\s]?\d{1,4}[-.\s]?\d{3}[-.\s]?\d{3,4}",
        ]
        for pattern in phone_patterns:
            m = re.search(pattern, text)
            if m:
                contact_info['phone'] = m.group()
                break

        # Extract linkedin
        for pattern in [
            r"linkedin\.com\/in\/[A-Za-z0-9_-]+",
            r"linkedin\.com\/pub\/[A-Za-z0-9_-]+",
        ]:
            m = re.search(pattern, text, re.I)
            if m:
                contact_info['linkedin'] = m.group()
                break
        
        # Extract github
        for pattern in [
            r"github\.com\/[A-Za-z0-9_-]+"
        ]:
            m = re.search(pattern, text, re.I)
            if m:
                contact_info['github'] = m.group()
                break

        # Extract website
        m = re.search(r"https?:\/\/[^\s]+", text)
        if m:
            site = m.group()
            if not any(x in site for x in ['linkedin', 'github']):
                contact_info['website'] = site

        return contact_info


    def find_section_boundaries(self, lines: List[str]) -> Dict[str, int]:
        section_indices = {}
        for i, line in enumerate(lines):
            line_clean = self.clean_text(line).lower()
            line_original = self.clean_text(line)
            if len(line_clean) < 3 or len(re.sub(r'[a-zA-Z]', '', line_clean)) > len(line_clean) * 0.7:
                continue
            if not section_indices.get('EXPERIENCE'):
                for k in self.experience_keywords:
                    if k in line_clean and self._is_section_header(line_original):
                        section_indices['EXPERIENCE'] = i
                        break
            if not section_indices.get('EDUCATION'):
                for k in self.education_keywords:
                    if k in line_clean and self._is_section_header(line_original):
                        section_indices['EDUCATION'] = i
                        break
            if not section_indices.get('SKILLS'):
                for k in self.skills_keywords:
                    if k in line_clean and self._is_section_header(line_original):
                        section_indices['SKILLS'] = i
                        break
            if not section_indices.get('CERTIFICATIONS'):
                for k in self.certification_keywords:
                    if k in line_clean and self._is_section_header(line_original):
                        section_indices['CERTIFICATIONS'] = i
                        break
            if not section_indices.get('PROJECTS'):
                for k in self.projects_keywords:
                    if k in line_clean and self._is_section_header(line_original):
                        section_indices['PROJECTS'] = i
                        break

            if not section_indices.get('SUMMARY'):
                for k in self.summary_keywords:
                    if k in line_clean and self._is_section_header(line_original):
                        section_indices['SUMMARY'] = i
                        break


        return section_indices

    """def _is_section_header(self, line: str) -> bool:
        if not line or len(line) > 50:
            return False
        if line.isupper() and len(line.split()) <= 5:
            return True
        words = line.split()
        if len(words) <= 5 and all(word[0].isupper() if word else False for word in words):
            return True
        if any(char in line for char in ['_', '=', '-']) and len(line.split()) <= 5:
            return True
        if line.endswith(':'):
            return True
        if len(words) <= 4 and not line.endswith('.') and len(line) < 40:
            return True
        return False"""
    
    def _is_section_header(self, line: str) -> bool:
        known_section_headers = [
            'experience', 'education', 'certifications',
            'skills', 'projects', 'summary'
        ]
        line_lower = line.strip().lower()
        if len(line) == 0 or len(line) > 50:
            return False
        # Check if line matches any known section header keywords exactly or partially
        for header in known_section_headers:
            if header in line_lower:
                return True
        return False


    """def extract_summary(self, lines: List[str], section_indices: Dict[str, int]) -> Tuple[str, int]:
        summary_start = 0
        for i, line in enumerate(lines[:10]):
            if line and any(keyword in line.lower() for keyword in ['summary', 'objective', 'profile', 'about']):
                summary_start = i + 1
                break
            elif i >= 3 and line and len(line.split()) > 5:
                summary_start = i
                break
        if summary_start == 0:
            summary_start = min(3, len(lines))
        summary_end = len(lines)
        if section_indices:
            first_section = min(section_indices.values())
            summary_end = min(summary_end, first_section)
        summary_lines = []
        for i in range(summary_start, summary_end):
            if i < len(lines):
                line = self.clean_text(lines[i])
                if line and not self._is_section_header(line):
                    summary_lines.append(line)
        summary = ' '.join(summary_lines)
        return summary, 0  # We now compute experience below, not from summary"""
    
    def extract_summary(self, lines: List[str], section_indices: Dict[str, int]) -> Tuple[str, int]:
        # If first line is section header, no summary exists
        if lines and self._is_section_header(lines[0]):
            # If the first detected section is SUMMARY, parse that instead
            if 'SUMMARY' in section_indices and section_indices['SUMMARY'] == 0:
            # set fallback to continue extracting below
                pass
            else:
                return "", 0  # no summary found
        
        # Prefer SUMMARY section if detected
        if 'SUMMARY' in section_indices:
            summary_start = section_indices['SUMMARY'] + 1
            # The end of summary is next section or end of document
            next_sections = [v for k,v in section_indices.items() if v > summary_start]
            summary_end = min(next_sections) if next_sections else len(lines)
        else:
            summary_start = None

            # Step 1: Find explicit summary header or dense first paragraph in first 10 lines
            for i, line in enumerate(lines[:10]):
                if line and any(k in line.lower() for k in ['summary', 'objective', 'profile', 'about']):
                    summary_start = i + 1
                    break
                elif i >= 0 and line and len(line.split()) > 10:
                    summary_start = i
                    break

            # Step 2: If no summary header or dense paragraph found, fallback to from line 0
            if summary_start is None:
                summary_start = 0

            summary_end = len(lines)

            # Step 3: Determine earliest section header start to limit summary extraction
            if section_indices:
                earliest_section = min(section_indices.values())
                if earliest_section > summary_start:
                    summary_end = earliest_section

        # Step 4: Extract non-header lines from summary_start to summary_end
        summary_lines = []
        for i in range(summary_start, summary_end):
            if i >= len(lines):
                break
            clean_line = self.clean_text(lines[i])
            if clean_line and not self._is_section_header(clean_line):
                summary_lines.append(clean_line)

        # Step 5: Join and return the summary text
        summary = ' '.join(summary_lines)

        return summary, 0  # Second value kept for compatibility
    
    def extract_projects(self, lines: List[str], section_indices: Dict[str, int]) -> List[dict]:
        if 'PROJECTS' not in section_indices:
            return []

        start_idx = section_indices['PROJECTS'] + 1
        # Find next section after projects
        following_sections = [v for v in section_indices.values() if v > start_idx]
        end_idx = min(following_sections) if following_sections else len(lines)

        project_lines = lines[start_idx:end_idx]
        projects = []
        current_project = {'title': '', 'details': []}

        for line in project_lines:
            clean_line = self.clean_text(line)
            # Heuristic: lines with bold/uppercase/title-like formatting can treat as new project title
            if self._is_section_header(clean_line) or (clean_line.isupper() and len(clean_line.split()) <= 5):
                if current_project['title'] or current_project['details']:
                    projects.append(current_project)
                current_project = {'title': clean_line, 'details': []}
            else:
                if clean_line:
                    current_project['details'].append(clean_line)

        if current_project['title'] or current_project['details']:
            projects.append(current_project)

        return projects



    def extract_experience(self, lines: List[str], section_indices: Dict[str, int]) -> List[Dict[str, Any]]:
        if 'EXPERIENCE' not in section_indices:
            return []
        exp_start = section_indices['EXPERIENCE'] + 1
        exp_end = len(lines)
        for section, idx in section_indices.items():
            if section != 'EXPERIENCE' and idx > exp_start:
                exp_end = min(exp_end, idx)
        exp_lines = lines[exp_start:exp_end]
        experiences = []
        current_job = None
        for line in exp_lines:
            line = self.clean_text(line)
            if not line:
                continue
            if self._is_job_header(line):
                if current_job:
                    experiences.append(current_job)
                current_job = self._parse_job_header(line)
            elif current_job and (
                line.startswith('•') or line.startswith('-') or line.startswith('*') or self._is_responsibility_line(line)
            ):
                responsibility = self.clean_text(line.lstrip('•-*').strip())
                if responsibility:
                    current_job['responsibilities'].append(responsibility)
            elif current_job and not self._is_job_header(line) and len(line.split()) > 3:
                if current_job['responsibilities']:
                    if line[0].islower():
                        current_job['responsibilities'][-1] += ' ' + line
                    else:
                        current_job['responsibilities'].append(line)
                else:
                    current_job['responsibilities'].append(line)
        if current_job:
            experiences.append(current_job)
        return experiences

    def _is_job_header(self, line: str) -> bool:
        if not line or len(line) < 10:
            return False
        date_patterns = [
            r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s*\d{4}',
            r'\d{1,2}/\d{4}',
            r'\d{4}\s*[-–]\s*\d{4}',
            r'\d{4}\s*[-–]\s*Present',
            r'Present',
            r'\d{4}\s*to\s*\d{4}',
            r'\d{4}\s*-\s*\d{4}',
        ]
        has_date = any(re.search(pattern, line, re.IGNORECASE) for pattern in date_patterns)
        if not has_date:
            return False
        has_separator = any(sep in line for sep in [' - ', ' – ', ' | ', ',', ' at '])
        has_title_indicator = any(indicator in line.lower() for indicator in self.job_title_indicators)
        return has_separator or has_title_indicator

    def _parse_job_header(self, line: str) -> Dict[str, Any]:
        job = {
            'company': '', 'title': '', 'location': '', 'duration': '', 'responsibilities': []
        }
        # Dates
        date_patterns = [
            r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s*\d{4}\s*[-–]\s*(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s*\d{4}|Present))',
            r'(\d{4}\s*[-–]\s*(?:\d{4}|Present))',
            r'(\d{1,2}/\d{4}\s*[-–]\s*(?:\d{1,2}/\d{4}|Present))'
        ]
        for pattern in date_patterns:
            date_match = re.search(pattern, line, re.IGNORECASE)
            if date_match:
                job['duration'] = date_match.group(1).strip()
                line = line.replace(date_match.group(1), '').strip()
                break
        line = re.sub(r'\s*[-–]\s*$', '', line)
        line = re.sub(r'^\s*[-–]\s*', '', line)
        match1 = re.match(r'^(.+?),\s*([A-Z][A-Za-z\s]+)\s*[-–]\s*(.+)$', line)
        if match1:
            job['company'] = match1.group(1).strip()
            job['location'] = match1.group(2).strip()
            job['title'] = match1.group(3).strip()
            return job
        match2 = re.match(r'^(.+?)\s*[-–]\s*(.+?),\s*([A-Z][A-Za-z\s]+)$', line)
        if match2:
            job['company'] = match2.group(1).strip()
            job['title'] = match2.group(2).strip()
            job['location'] = match2.group(3).strip()
            return job
        match3 = re.search(r'^(.+?)\s+at\s+(.+?)(?:,\s*(.+?))?$', line, re.IGNORECASE)
        if match3:
            job['title'] = match3.group(1).strip()
            job['company'] = match3.group(2).strip()
            if match3.group(3):
                job['location'] = match3.group(3).strip()
            return job
        if ' - ' in line or ' – ' in line:
            parts = re.split(r'\s*[-–]\s*', line, 1)
            if len(parts) == 2:
                part1, part2 = parts[0].strip(), parts[1].strip()
                company_indicators = ['inc', 'corp', 'llc', 'ltd', 'company', 'group', 'firm']
                if any(indicator in part1.lower() for indicator in company_indicators):
                    job['company'] = part1
                    job['title'] = part2
                else:
                    job['company'] = part1
                    job['title'] = part2
        if not job['company'] and not job['title']:
            job['title'] = line
        return job

    def _is_responsibility_line(self, line: str) -> bool:
        if len(line.split()) < 4:
            return False
        if self._is_section_header(line):
            return False
        action_verbs = [
            'led', 'managed', 'developed', 'created', 'implemented', 'designed',
            'analyzed', 'coordinated', 'supervised', 'maintained', 'improved',
            'increased', 'decreased', 'reduced', 'optimized', 'streamlined',
            'established', 'built', 'executed', 'delivered', 'achieved'
        ]
        line_lower = line.lower()
        has_action_verb = any(verb in line_lower for verb in action_verbs)
        return has_action_verb or len(line.split()) > 8

    def extract_education(self, lines: List[str], section_indices: Dict[str, int]) -> List[Dict[str, str]]:
        if 'EDUCATION' not in section_indices:
            return []
        edu_start = section_indices['EDUCATION'] + 1
        edu_end = len(lines)
        for section, idx in section_indices.items():
            if section != 'EDUCATION' and idx > edu_start:
                edu_end = min(edu_end, idx)
        edu_lines = lines[edu_start:edu_end]
        education = []
        current_edu = {}
        degree_keywords = [
            'bachelor', 'master', 'phd', 'doctorate', 'associate', 'diploma',
            'certificate', 'bs', 'ba', 'ms', 'ma', 'mba', 'phd', 'md', 'jd',
            'bsc', 'msc', 'beng', 'meng', 'btech', 'mtech'
        ]
        institution_keywords = [
            'university', 'college', 'institute', 'school', 'academy',
            'polytechnic', 'conservatory'
        ]
        for line in edu_lines:
            line = self.clean_text(line)
            if not line or len(line) < 5:
                continue
            line_lower = line.lower()
            has_institution = any(keyword in line_lower for keyword in institution_keywords)
            has_degree = any(keyword in line_lower for keyword in degree_keywords)
            year_pattern = r'(\d{4})(?:\s*[-–]\s*(\d{4}))?'
            year_match = re.search(year_pattern, line)
            years = ''
            if year_match:
                if year_match.group(2):
                    years = f"{year_match.group(1)}-{year_match.group(2)}"
                else:
                    years = year_match.group(1)
            if has_institution:
                if current_edu and current_edu.get('institution'):
                    education.append(current_edu)
                current_edu = {
                    'institution': line,
                    'degree': '',
                    'field': '',
                    'years': years,
                    'gpa': ''
                }
            elif has_degree:
                if current_edu:
                    current_edu['degree'] = line
                    if years and not current_edu['years']:
                        current_edu['years'] = years
                else:
                    current_edu = {
                        'institution': '',
                        'degree': line,
                        'field': '',
                        'years': years,
                        'gpa': ''
                    }
            gpa_match = re.search(r'gpa:?\s*(\d+\.?\d*)', line, re.IGNORECASE)
            if gpa_match and current_edu:
                current_edu['gpa'] = gpa_match.group(1)
        if current_edu and (current_edu.get('institution') or current_edu.get('degree')):
            education.append(current_edu)
        return education
    
    def extract_skills(self, lines: List[str], section_indices: Dict[str, int]) -> List[str]:
        """
        Extract all skills appearing in the 'SKILLS' section, separated by any common delimiter,
        and ignore categories. Stops at the next identified section.
        """
        skills = []
        if 'SKILLS' in section_indices:
            skills_start = section_indices['SKILLS'] + 1
            skills_end = len(lines)
            for section, idx in section_indices.items():
                if section != 'SKILLS' and idx > skills_start:
                    skills_end = min(skills_end, idx)
            skills_lines = lines[skills_start:skills_end]
            skills_text = ' '.join(skills_lines)
            # Use all common delimiters to split the skill string
            pattern = r'[:,\|;•·\n/\\\\]+'
            raw_skills = [skill.strip() for skill in re.split(pattern, skills_text) if skill.strip() and len(skill.strip()) > 1]
            # Optionally deduplicate and filter out very short tokens
            skills = list(dict.fromkeys([s for s in raw_skills if len(s) > 1]))
        return skills


    """def extract_skills(self, lines: List[str], section_indices: Dict[str, int], full_text: str) -> Tuple[List[str], List[str]]:
        technical_skills = set()
        tools_technologies = set()
        if 'SKILLS' in section_indices:
            skills_start = section_indices['SKILLS'] + 1
            skills_end = len(lines)
            for section, idx in section_indices.items():
                if section != 'SKILLS' and idx > skills_start:
                    skills_end = min(skills_end, idx)
            skills_lines = lines[skills_start:skills_end]
            skills_text = ' '.join(skills_lines)
            category_patterns = [
                r'([A-Za-z\s]+):\s*([^:\n]+)',
                r'([A-Za-z\s]+)[-–]\s*([^:\n]+)',
            ]
            for pattern in category_patterns:
                matches = re.findall(pattern, skills_text, re.MULTILINE)
                for category, skills_str in matches:
                    category_lower = category.lower().strip()
                    skills_list = self._parse_skill_list(skills_str)
                    if any(keyword in category_lower for keyword in
                           ['technical', 'programming', 'development', 'analytics', 'database', 'languages']):
                        technical_skills.update(skills_list)
                    else:
                        tools_technologies.update(skills_list)
            if not technical_skills and not tools_technologies:
                all_skills = self._parse_skill_list(skills_text)
                for skill in all_skills:
                    if self._is_technical_skill(skill):
                        technical_skills.add(skill)
                    else:
                        tools_technologies.add(skill)
        
        return list(technical_skills), list(tools_technologies)"""

    def _parse_skill_list(self, skills_text: str) -> List[str]:
        if not skills_text:
            return []
        skills_text = self.clean_text(skills_text)
        delimiters = [',', '|', ';', '•', '·', '\n', '/', '\\']
        for delimiter in delimiters:
            if delimiter in skills_text:
                skills = [skill.strip() for skill in skills_text.split(delimiter)]
                skills = [skill for skill in skills if skill and len(skill) > 1]
                if skills:
                    return skills
        words = skills_text.split()
        if len(words) > 10:
            return [word for word in words if len(word) > 2]
        else:
            return [skills_text] if skills_text else []

    """def _is_technical_skill(self, skill: str) -> bool:
        skill_lower = skill.lower()
        tech_indicators = [
            'script', 'lang', 'programming', '.js', '.py', '.java',
            'framework', 'library', 'api', 'sdk', 'engine', 'algorithm',
            'machine learning', 'deep learning', 'neural network',
            'data structure', 'database', 'sql', 'nosql'
        ]
        if any(indicator in skill_lower for indicator in tech_indicators):
            return True
        for category, skills in self.technical_skill_categories.items():
            if skill_lower in [s.lower() for s in skills]:
                return category in [
                    'programming_languages', 'databases', 'frameworks', 'ai_ml_tools', 'analytics_tools']
        return False"""

    def extract_certifications(self, lines: List[str], section_indices: Dict[str, int], full_text: str) -> List[str]:
        certifications = set()
        if 'CERTIFICATIONS' in section_indices:
            cert_start = section_indices['CERTIFICATIONS'] + 1
            cert_end = len(lines)
            for section, idx in section_indices.items():
                if section != 'CERTIFICATIONS' and idx > cert_start:
                    cert_end = min(cert_end, idx)
            cert_lines = lines[cert_start:cert_end]
            cert_text = ' '.join(cert_lines)
            cert_delimiters = ['|', ',', ';', '\n', '•', '·']
            for delimiter in cert_delimiters:
                if delimiter in cert_text:
                    certs = [cert.strip() for cert in cert_text.split(delimiter)]
                    for cert in certs:
                        if cert and len(cert) > 3:
                            cert_clean = re.sub(r'\([^)]*\)', '', cert).strip()
                            cert_clean = re.sub(r'\d{4}', '', cert_clean).strip()
                            if cert_clean:
                                certifications.add(cert_clean)
                    break
        cert_patterns = [
            r'([A-Z][A-Za-z\s]+(?:Certified|Certification|Certificate))',
            r'(PMP|PMI|CISSP|CISA|CISM|CPA|CFA|FRM|SHRM|PHR)',
            r'([A-Z]+\s+Certified\s+[A-Za-z\s]+)',
            r'(Microsoft\s+Certified\s+[^,\n]+)',
            r'(AWS\s+Certified\s+[^,\n]+)',
            r'(Google\s+[^,\n]+\s+Certificate)',
            r'(CompTIA\s+[A-Z]+)',
            r'(Cisco\s+[A-Z]+)',
            r'(Oracle\s+Certified\s+[^,\n]+)',
            r'(Salesforce\s+Certified\s+[^,\n]+)'
        ]
        for pattern in cert_patterns:
            matches = re.findall(pattern, full_text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                match_clean = match.strip()
                if len(match_clean) > 3:
                    certifications.add(match_clean)
        return list(certifications)
    
    async def extract_keywords_ollama(self, text: str) -> list:
        client = AsyncClient()
        prompt = (
            """CRITICAL: You MUST return ONLY valid JSON. NO explanations, NO additional text, NO markdown formatting.

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

            ANALYZE THIS JOB DESCRIPTION:"""
            + text
        )
        try:
            response = await client.chat("phi4:latest", messages=[{"role": "user", "content": prompt}])
            
            response_content = response.get('message', {}).get('content', '')
            logger.info(f"Ollama raw response: {response_content}")

            # Use regex to find the JSON object (starts with { and ends with })
            object_match = re.search(r'\{.*\}', response_content, re.DOTALL)
            if not object_match:
                logger.error("Could not find a valid JSON object in the Ollama response.")
                return []
            
            json_object_str = object_match.group(0)
            
            try:
                # Parse and return the full categorized data object
                data = json.loads(json_object_str)
                return data

            except json.JSONDecodeError as e:
                logger.error(f"JSON loads failed: {e}")
                return {}

        except Exception as e:
            logger.error(f"Keyword extraction failed with an unexpected error: {e}")
            return {}
        
    async def augment_keywords(self, parsed_resume: dict) -> dict:
        """
        Use the keywords extracted from searchable_ollama_content as the final combined keywords.
        No need to merge with existing 'skills' list.
        """
        extracted_keywords = await self.extract_keywords_ollama(parsed_resume.get("searchable_ollama_content", ""))
        parsed_resume["combined_keywords"] = list(extracted_keywords)
        return parsed_resume


    def calculate_total_experience(self, experiences):
        total_months = 0
        def extract_dates(duration_str):
            patterns = [
                r'([A-Za-z]{3,9} \d{4})\s*[-–]\s*([A-Za-z]{3,9} \d{4}|Present)',
                r'(\d{4})\s*[-–]\s*(\d{4}|Present)',
                r'(\d{2}/\d{4})\s*[-–]\s*(\d{2}/\d{4}|Present)'
            ]
            for p in patterns:
                m = re.search(p, duration_str)
                if m:
                    start, end = m.groups()
                    try:
                        start_date = date_parser.parse(start, default=date_parser.parse("Jan 1"))
                        end_date = datetime.now() if end.strip().lower() == "present" else date_parser.parse(end, default=date_parser.parse("Jan 1"))
                        months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)
                        return max(months, 0)
                    except Exception:
                        return 0
            return 0
        for exp in experiences:
            dur = exp.get('duration','')
            months = extract_dates(dur) if dur else 0
            total_months += months
        years = total_months // 12
        months = total_months % 12
        return f"{years} years, {months} months" if years or months else "0 years, 0 months"

    def parse_resume(self, resume_text: str, file_name: str = "resume.pdf") -> dict:
        contact_info = self.extract_contact_info(resume_text)
        lines = [line.strip() for line in resume_text.split('\n') if line.strip()]
        section_indices = self.find_section_boundaries(lines)
        summary, _ = self.extract_summary(lines, section_indices)
        experiences = self.extract_experience(lines, section_indices)
        education = self.extract_education(lines, section_indices)
        projects = self.extract_projects(lines, section_indices)
        certifications = self.extract_certifications(lines, section_indices, resume_text)
        """technical_skills, tools_technologies = self.extract_skills(lines, section_indices, resume_text)
        skills = list(technical_skills) + list(tools_technologies)"""
        skills = self.extract_skills(lines, section_indices)
        current_title = experiences[0]['title'] if experiences else ""
        total_experience_years = self.calculate_total_experience(experiences)
        all_skills_text = ' '.join(skills)
        
        all_experience_text = ' '.join(
            ' '.join(exp.get('responsibilities', [])) for exp in experiences
        )
    
        # Concatenate only details from projects (list of strings)
        all_project_text = ' '.join(
            ' '.join(proj.get('details', [])) for proj in projects
        )
        """all_experience_text = ' '.join([
            f"{exp.get('company', '')} {exp.get('title', '')} {exp.get('duration', '')} {' '.join(exp.get('responsibilities', []))}" 
            for exp in experiences
        ])"""
        """all_project_text = ' '.join([
            f"{prj.get('title', '')} {' '.join(prj.get('details', []))}" 
            for prj in projects
        ])"""
        all_education_text = ' '.join([
            f"{edu.get('institution', '')} {edu.get('degree', '')}{edu.get('gpa', '')}" 
            for edu in education
        ])
        all_certifications_text = ' '.join(certifications)
        searchable_content = " ".join([
            summary,
            all_skills_text, all_experience_text,
            all_project_text, all_certifications_text
        ])
        searchable_ollama_content = " ".join([
            summary,
            all_experience_text, all_project_text,
            all_skills_text
        ])
        parsed_resume = {
            'file_name': file_name,
            'name': contact_info.get('name',''),
            'phone': contact_info.get('phone',''),
            'email': contact_info.get('email',''),
            'linkedin': contact_info.get('linkedin',''),
            'location': contact_info.get('location',''),
            'github': contact_info.get('github',''),
            'website': contact_info.get('website',''),
            'summary': summary,
            'total_experience_years': total_experience_years,
            'current_title': current_title,
            'experiences': experiences,
            'education': education,
            'certifications': certifications,
            'skills': skills,
            'projects': projects,
            'all_skills_text': all_skills_text,
            'all_experience_text': all_experience_text,
            'all_project_text': all_project_text,
            'all_education_text': all_education_text,
            'all_certifications_text': all_certifications_text,
            'searchable_content': searchable_content,
            'searchable_ollama_content': searchable_ollama_content,
            'parsing_metadata': {
                'parsing_timestamp': datetime.now().isoformat(),
                'parser_version': "2.0"
            }
        }
        return parsed_resume
