import React, { useState, useEffect } from 'react';
import axios from 'axios';
import 'bootstrap/dist/css/bootstrap.min.css';
import './App.css';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Container, Row, Col, Form, Button, Card, 
  Navbar, Nav, Alert, Spinner, ListGroup, Badge, Modal 
} from 'react-bootstrap';
import { FiUpload, FiFileText, FiSearch, FiAward, FiMenu } from 'react-icons/fi';

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:5000';

// --- Animation Variants ---
const fadeVariants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { duration: 0.5 } }
};

const resultItemVariants = {
  hidden: { opacity: 0, x: -50 },
  visible: { opacity: 1, x: 0 },
};

// --- NEW: A helper component for rendering the report details ---
const ReportSection = ({ title, keywordsData }) => {
  if (!keywordsData || Object.keys(keywordsData).length === 0) return null;

  return (
    <>
      <h5 className="mt-3">{title}</h5>
      {Object.entries(keywordsData).map(([category, details]) => (
        (details.matched.length > 0 || details.missing.length > 0) && (
          <div key={category} className="mb-3">
            <strong>{category.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</strong>
            <div className="mt-1">
              {details.matched.map(kw => <Badge key={kw} bg="success" className="me-1 mb-1 fw-normal">{kw}</Badge>)}
              {details.missing.map(kw => <Badge key={kw} bg="secondary" className="me-1 mb-1 fw-normal">{kw}</Badge>)}
            </div>
          </div>
        )
      ))}
    </>
  );
};

function App() {
  // --- Tabs ---
  const [activeTab, setActiveTab] = useState('landing');

  // --- States ---
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [jdText, setJdText] = useState('');
  const [topK, setTopK] = useState(10);
  const [matchedResults, setMatchedResults] = useState([]);
  // --- NEW: State for the detailed report modal ---
  const [showReportModal, setShowReportModal] = useState(false);
  const [selectedCandidate, setSelectedCandidate] = useState(null);

  const [extractedKeywords, setExtractedKeywords] = useState(null);
  const [loading, setLoading] = useState(false);
  const [uploadLoading, setUploadLoading] = useState(false);
  const [isExtracting, setIsExtracting] = useState(false);
  const [alert, setAlert] = useState({ show: false, message: '', type: 'info' });
  const [stats, setStats] = useState({ total_resumes_loaded: 0, model_ready: false });
  const [isDragging, setIsDragging] = useState(false);

  useEffect(() => {
    checkApiHealth();
    fetchStats();
  }, []);

  const checkApiHealth = async () => {
    try { await axios.get(`${API_BASE_URL}/health`); } 
    catch { showAlert('⚠️ Backend API is not running. Please start the backend server.', 'danger'); }
  };
  const fetchStats = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/stats`);
      setStats(response.data);
    } catch { showAlert('⚠️ Failed to refresh statistics.', 'warning'); }
  };
  const showAlert = (message, type='info') => {
    setAlert({ show: true, message, type });
    if (type !== 'danger') {
      setTimeout(() => setAlert({ show: false, message: '', type: 'info' }), 6000);
    }
  };

  // --- File Handlers ---
  const handleFileChange = files => setSelectedFiles(Array.from(files));
  const handleDragOver = e => { e.preventDefault(); setIsDragging(true); };
  const handleDragLeave = e => { e.preventDefault(); setIsDragging(false); };
  const handleDrop = e => { e.preventDefault(); setIsDragging(false); handleFileChange(e.dataTransfer.files); };

  const uploadResumes = async () => {
    if(selectedFiles.length===0) { showAlert('Select at least one resume.', 'warning'); return; }
    setUploadLoading(true);
    try {
      const formData = new FormData();
      selectedFiles.forEach(f=>formData.append('files',f));
      const response = await axios.post(`${API_BASE_URL}/upload_resumes`, formData, { headers:{'Content-Type':'multipart/form-data'} });
      showAlert(`✅ Successfully uploaded ${response.data.total_processed} resumes!`, 'success');
      setSelectedFiles([]); document.getElementById('file-input').value='';
      setTimeout(fetchStats, 1000);
    } catch { showAlert('❌ Error uploading resumes.', 'danger'); }
    finally { setUploadLoading(false); }
  };

  // --- JD Keyword Extraction ---
  const handleExtractKeywords = async () => {
    if(!jdText.trim()) { showAlert('Enter a JD first.', 'warning'); return; }
    setIsExtracting(true); setExtractedKeywords(null);
    try {
      const response = await axios.post(`${API_BASE_URL}/extract-keywords`, { job_description: jdText });
      setExtractedKeywords(response.data); showAlert('✅ Keywords extracted!', 'success');
    } catch { showAlert('❌ Error extracting keywords.', 'danger'); }
    finally { setIsExtracting(false); }
  };

  // --- Top Matches ---
  const getMatches = async () => {
    // New checks: ensure keywords have been extracted first.
    if (!jdText.trim()) { showAlert('Please enter a Job Description.', 'warning'); return; }
    if (!extractedKeywords) { showAlert('Please extract keywords before finding matches.', 'warning'); return; }
    if (stats.total_resumes_loaded === 0) { showAlert('Upload some resumes first.', 'warning'); return; }
    
    setLoading(true);
    try {
      // The payload now sends the 'keywords' object instead of the raw 'jd' text.
      const payload = { keywords: extractedKeywords, top_k: topK };
      const response = await axios.post(`${API_BASE_URL}/match`, payload);
      
      // --- CHANGED: Implemented safer result handling ---
      const results = response.data.results || [];
      setMatchedResults(results); 
      
      if (results.length > 0) {
        showAlert(`✅ Found ${results.length} matches!`, 'success');
        setActiveTab('matches'); // Automatically switch to the matches tab on success
      } else {
        showAlert('ℹ️ No matching resumes found for the given keywords.', 'info');
      }
    } catch { showAlert('❌ Error getting matches.', 'danger'); }
    finally { setLoading(false); }
  };

  const getScoreColor = score => score>=0.7?'success':score>=0.4?'warning':'secondary';

  // --- NEW: Functions to handle the modal ---
  const handleShowReport = (candidate) => {
    setSelectedCandidate(candidate);
    setShowReportModal(true);
  };
  const handleCloseReport = () => setShowReportModal(false);

  return (
    <Container fluid className="py-3">

      {/* --- Responsive Navbar --- */}
      <Navbar expand="lg" className="custom-navbar mb-4" variant="dark">
        <Navbar.Brand className="fw-bold">🎯 Resume Matcher</Navbar.Brand>
        <Navbar.Toggle aria-controls="nav-links"><FiMenu /></Navbar.Toggle>
        <Navbar.Collapse id="nav-links">
          <Nav className="ms-auto">
            <Nav.Link active={activeTab==='landing'} onClick={()=>setActiveTab('landing')}>Home</Nav.Link>
            <Nav.Link active={activeTab==='resume'} onClick={()=>setActiveTab('resume')}>Resume</Nav.Link>
            <Nav.Link active={activeTab==='job'} onClick={()=>setActiveTab('job')}>Job Description</Nav.Link>
            <Nav.Link active={activeTab==='matches'} onClick={()=>setActiveTab('matches')}>Matches</Nav.Link>
          </Nav>
        </Navbar.Collapse>
      </Navbar>

      {/* --- Alerts --- */}
      <AnimatePresence>
        {alert.show && (
          <motion.div initial={{opacity:0,y:-20}} animate={{opacity:1,y:0}} exit={{opacity:0,y:-20}}>
            <Alert variant={alert.type} dismissible onClose={()=>setAlert({...alert, show:false})} className="shadow-sm">
              {alert.message}
            </Alert>
          </motion.div>
        )}
      </AnimatePresence>

      {/* --- Sections --- */}
      <AnimatePresence mode="wait">
        {/* --- Landing Page --- */}
        {activeTab==='landing' && (
          <motion.div key="landing" variants={fadeVariants} initial="hidden" animate="visible" exit="hidden">
            <div className="landing-page text-center">
              <h2 className="fw-bold">Welcome to Universal Resume Matcher</h2>
              <p className="text-muted">Upload resumes, extract JD keywords, and find top matches instantly.</p>
              <Row className="mt-4 justify-content-center">
                <Col className="landing-step"><FiUpload size={48} /><h6>Upload Resumes</h6></Col>
                <Col className="landing-arrow"><FiSearch size={32} /></Col>
                <Col className="landing-step"><FiFileText size={48} /><h6>Paste JD</h6></Col>
                <Col className="landing-arrow"><FiSearch size={32} /></Col>
                <Col className="landing-step"><FiAward size={48} /><h6>Top Matches</h6></Col>
              </Row>
            </div>
          </motion.div>
        )}

        {/* --- Resume Upload Tab --- */}
        {activeTab==='resume' && (
          <motion.div key="resume" variants={fadeVariants} initial="hidden" animate="visible" exit="hidden">
            <Card>
              <Card.Header><h4>📤 Upload Resumes</h4></Card.Header>
              <Card.Body>
                <div
                  className={`upload-section text-center ${isDragging ? 'drag-over' : ''}`}
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                  onClick={() => document.getElementById('file-input').click()}
                >
                  <input id="file-input" type="file" multiple accept=".pdf,.docx,.txt" onChange={(e)=>handleFileChange(e.target.files)} style={{display:'none'}}/>
                  <h5>Drag & Drop Files Here</h5>
                  <p className="text-muted">or click to select files (PDF, DOCX, TXT)</p>
                </div>

                {selectedFiles.length>0 && (
                  <div className="mt-3">
                    <h6>Selected Files ({selectedFiles.length}):</h6>
                    <ListGroup style={{maxHeight:'150px', overflowY:'auto'}}>
                      {selectedFiles.slice(0,5).map((file,i)=>(
                        <ListGroup.Item key={i} className="d-flex justify-content-between align-items-center">
                          <span>{file.name}</span>
                          <Badge bg="info">{(file.size/1024).toFixed(1)} KB</Badge>
                        </ListGroup.Item>
                      ))}
                      {selectedFiles.length>5 && <ListGroup.Item className="text-muted">+ {selectedFiles.length-5} more files</ListGroup.Item>}
                    </ListGroup>
                  </div>
                )}

                <div className="d-grid mt-3">
                  <Button variant="primary" onClick={uploadResumes} disabled={uploadLoading || selectedFiles.length===0} size="lg">
                    {uploadLoading ? <> <Spinner size="sm" className="me-2"/>Uploading... </> : <>📤 Upload {selectedFiles.length} File(s)</>}
                  </Button>
                </div>
              </Card.Body>
            </Card>
          </motion.div>
        )}

        {/* --- Job Description Tab --- */}
        {activeTab==='job' && (
          <motion.div key="job" variants={fadeVariants} initial="hidden" animate="visible" exit="hidden">
            <Card>
              <Card.Header><h4>🎯 Job Description</h4></Card.Header>
              <Card.Body>
                <Form.Group className="mb-3">
                  <Form.Label>Paste Job Description</Form.Label>
                  <Form.Control as="textarea" rows={8} value={jdText} onChange={e=>setJdText(e.target.value)} placeholder="Paste job description here..."/>
                </Form.Group>
                <Row className="mb-3">
                  <Col md={4}>
                    <Form.Group>
                      <Form.Label>Number of Top Matches</Form.Label>
                      <Form.Control type="number" value={topK} min={1} max={50} onChange={e=>setTopK(parseInt(e.target.value)||1)} />
                    </Form.Group>
                  </Col>
                </Row>
                <div className="d-grid gap-2">
                  <Button variant="info" onClick={handleExtractKeywords} disabled={isExtracting || !jdText.trim()} size="lg" className="text-white">
                    {isExtracting ? <> <Spinner size="sm" className="me-2"/>Extracting... </> : '🔬 Extract Keywords'}
                  </Button>
                  <Button variant="success" onClick={getMatches} disabled={loading || stats.total_resumes_loaded===0} size="lg">
                    {loading ? <> <Spinner size="sm" className="me-2"/>Finding Matches... </> : '🔍 Find Top Matches'}
                  </Button>
                </div>
              </Card.Body>
            </Card>

            {/* Extracted Keywords Card */}
            {extractedKeywords && (
              <Card className="mt-3">
                <Card.Header><h5>🔑 Extracted Job Keywords</h5></Card.Header>
                <Card.Body>
                  <Row>
                    <Col md={6}>
                      <h6>Required</h6>
                      {extractedKeywords.required_keywords && Object.entries(extractedKeywords.required_keywords).map(([cat,list])=>list.length>0&&(
                        <div key={cat} className="mb-2"><strong>{cat.replace(/_/g,' ')}:</strong> <p className="text-muted">{list.join(', ')}</p></div>
                      ))}
                    </Col>
                    <Col md={6}>
                      <h6>Preferred</h6>
                      {extractedKeywords.preferred_keywords && Object.entries(extractedKeywords.preferred_keywords).map(([cat,list])=>list.length>0&&(
                        <div key={cat} className="mb-2"><strong>{cat.replace(/_/g,' ')}:</strong> <p className="text-muted">{list.join(', ')}</p></div>
                      ))}
                    </Col>
                  </Row>
                </Card.Body>
              </Card>
            )}
          </motion.div>
        )}

        {/* --- Top Matches Tab --- */}
        {activeTab === 'matches' && (
          <motion.div key="matches" variants={fadeVariants} initial="hidden" animate="visible" exit="hidden">
            {matchedResults.length > 0 ? (
              <Card>
                <Card.Header><h4>🏆 Top {matchedResults.length} Matches</h4></Card.Header>
                <ListGroup variant="flush">
                  {matchedResults.map((result, idx) => (
                    <motion.div key={result.resume_id} variants={resultItemVariants} custom={idx} initial="hidden" animate="visible" transition={{ delay: idx * 0.1 }}>
                      <ListGroup.Item>
                        <Row className="align-items-center">
                          <Col md={9}>
                            <h5 className="mb-1">{result.name}</h5>
                            <p className="text-muted mb-1">{result.current_title || 'No title specified'}</p>
                            <p className="summary-text">{result.summary || 'No summary available.'}</p>
                            
                            {/* --- CHANGED: Added Detailed Report button --- */}
                            <Button variant="outline-primary" size="sm" className="mt-2" onClick={() => handleShowReport(result)}>
                              View Detailed Report
                            </Button>
                          </Col>
                          <Col md={3} className="text-md-end text-center mt-3 mt-md-0">
                            <div className="score-circle" style={{ background: `conic-gradient(#28a745 ${result.score * 360}deg, #e9ecef 0deg)` }}>
                                <span>{Math.round(result.score * 100)}</span>
                            </div>
                            <small className="text-muted">Match Score</small>
                          </Col>
                        </Row>
                      </ListGroup.Item>
                    </motion.div>
                  ))}
                </ListGroup>
              </Card>
            ) : (
              <Card className="empty-state text-center p-5"> {/* ... (no changes) ... */ } </Card>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* --- NEW: The Detailed Report Modal Component --- */}
      {selectedCandidate && (
        <Modal show={showReportModal} onHide={handleCloseReport} size="lg" centered>
          <Modal.Header closeButton>
            <Modal.Title>Detailed Report for {selectedCandidate.name}</Modal.Title>
          </Modal.Header>
          <Modal.Body>
            <p>This report shows the keywords from the job description and indicates which ones were found in the candidate's resume. The score is calculated based only on the "Scoring Keywords" section.</p>
            <div className="d-flex align-items-center mb-3">
              <Badge bg="success" className="me-2">Matched</Badge>
              <Badge bg="secondary" className="me-2">Not Found</Badge>
            </div>
            <hr/>
            <ReportSection 
              title="Scoring Keywords"
              keywordsData={selectedCandidate.report_details.scoring_keywords} 
            />
            <hr/>
            <ReportSection 
              title="Additional Keywords (for context)"
              keywordsData={selectedCandidate.report_details.additional_keywords}
            />
          </Modal.Body>
          <Modal.Footer>
            <Button variant="secondary" onClick={handleCloseReport}>
              Close
            </Button>
          </Modal.Footer>
        </Modal>
      )}
    </Container>
  );
}

export default App;
