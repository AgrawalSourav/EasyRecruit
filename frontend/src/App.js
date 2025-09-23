import React, { useState, useEffect, createContext, useContext } from 'react';
import { BrowserRouter as Router, Routes, Route, Link, Navigate, useNavigate } from 'react-router-dom';
import axios from 'axios';
import 'bootstrap/dist/css/bootstrap.min.css';
import './App.css';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Container, Row, Col, Form, Button, Card, 
  Alert, Spinner, ListGroup, Badge, Modal, ProgressBar 
} from 'react-bootstrap';
import { 
  FiUpload, FiFileText, FiSearch, FiAward, FiLogOut, 
  FiUser, FiTarget, FiTrendingUp, FiDownload, FiEye,
  FiCheckCircle, FiClock, FiZap, FiEyeOff
} from 'react-icons/fi';

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:5000';

// Axios configuration to send cookies with requests
const apiClient = axios.create({
    baseURL: API_BASE_URL,
    withCredentials: true
});

// Animation Variants
const fadeVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.6, ease: "easeOut" } }
};

const slideInVariants = {
  hidden: { opacity: 0, x: -30 },
  visible: { opacity: 1, x: 0, transition: { duration: 0.5 } }
};

const staggerContainer = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1
    }
  }
};

// Helper component for rendering the report details
const ReportSection = ({ title, keywordsData }) => {
  if (!keywordsData || Object.keys(keywordsData).length === 0) return null;

  return (
    <>
      <h5 className="mt-4 mb-3 text-primary">{title}</h5>
      {Object.entries(keywordsData).map(([category, details]) => (
        (details.matched.length > 0 || details.missing.length > 0) && (
          <div key={category} className="mb-3 p-3 bg-light rounded">
            <h6 className="fw-bold text-dark mb-2">
              {category.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
            </h6>
            <div className="d-flex flex-wrap gap-1">
              {details.matched.map(kw => 
                <Badge key={kw} bg="success" className="fw-normal px-2 py-1">{kw}</Badge>
              )}
              {details.missing.map(kw => 
                <Badge key={kw} bg="secondary" className="fw-normal px-2 py-1">{kw}</Badge>
              )}
            </div>
          </div>
        )
      ))}
    </>
  );
};

// Authentication Context
const AuthContext = createContext(null);

const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        apiClient.get('/@me').then(response => {
            setUser(response.data.user);
        }).catch(() => {
            setUser(null);
        }).finally(() => {
            setLoading(false);
        });
    }, []);

    const login = async (email, password) => {
        const response = await apiClient.post('/login', { email, password });
        setUser(response.data.user);
    };

    const register = async (email, password) => {
        await apiClient.post('/register', { email, password });
    };

    const logout = async () => {
        await apiClient.post('/logout');
        setUser(null);
    };

    const value = { user, login, register, logout, loading };

    return <AuthContext.Provider value={value}>{!loading && children}</AuthContext.Provider>;
};

const useAuth = () => useContext(AuthContext);

const ProtectedRoute = ({ children }) => {
    const { user } = useAuth();
    if (!user) {
        return <Navigate to="/login" />;
    }
    return children;
};

// Login Page Component
const LoginPage = () => {
    const navigate = useNavigate();
    const { login, register} = useAuth();
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [isRegistering, setIsRegistering] = useState(false);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        try {
            if (isRegistering) {
                await register(email, password);
                await login(email, password);
            } else {
                await login(email, password);
            }
            navigate('/');
        } catch (err) {
            setError(err.response?.data?.error || 'An error occurred.');
        }
    };

    return (
        <div className="min-vh-100 d-flex align-items-center justify-content-center" 
             style={{ background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' }}>
            <Container>
                <Row className="justify-content-center">
                    <Col md={6} lg={4}>
                        <motion.div
                            initial={{ opacity: 0, y: 50 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.8 }}
                        >
                            <Card className="shadow-lg border-0 rounded-4">
                                <Card.Body className="p-5">
                                    <div className="text-center mb-4">
                                        <div className="mb-3">
                                            <FiTarget size={48} className="text-primary" />
                                        </div>
                                        <h2 className="fw-bold text-dark mb-2">Resume Matcher</h2>
                                        <p className="text-muted">
                                            {isRegistering ? 'Create your account' : 'Welcome back'}
                                        </p>
                                    </div>
                                    
                                    {error && <Alert variant="danger" className="rounded-3">{error}</Alert>}
                                    
                                    <Form onSubmit={handleSubmit}>
                                        <Form.Group className="mb-3">
                                            <Form.Label className="fw-semibold">Email</Form.Label>
                                            <Form.Control 
                                                type="email" 
                                                value={email} 
                                                onChange={e => setEmail(e.target.value)} 
                                                required 
                                                className="rounded-3 py-2"
                                                placeholder="Enter your email"
                                            />
                                        </Form.Group>
                                        <Form.Group className="mb-4">
                                            <Form.Label className="fw-semibold">Password</Form.Label>
                                            <Form.Control 
                                                type="password" 
                                                value={password} 
                                                onChange={e => setPassword(e.target.value)} 
                                                required 
                                                className="rounded-3 py-2"
                                                placeholder="Enter your password"
                                            />
                                        </Form.Group>
                                        <Button 
                                            type="submit" 
                                            className="w-100 py-2 fw-semibold rounded-3" 
                                            size="lg"
                                            style={{ background: 'linear-gradient(45deg, #667eea, #764ba2)' }}
                                        >
                                            {isRegistering ? 'Create Account' : 'Sign In'}
                                        </Button>
                                    </Form>
                                    
                                    <div className="text-center mt-4">
                                        <Button 
                                            variant="link" 
                                            onClick={() => setIsRegistering(!isRegistering)}
                                            className="text-decoration-none"
                                        >
                                            {isRegistering ? 'Already have an account? Sign In' : "Don't have an account? Register"}
                                        </Button>
                                    </div>
                                </Card.Body>
                            </Card>
                        </motion.div>
                    </Col>
                </Row>
            </Container>
        </div>
    );
};

// Main Application Component
const MainApp = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  // States
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [jdText, setJdText] = useState('');
  const [topK, setTopK] = useState(10);
  const [matchedResults, setMatchedResults] = useState([]);
  const [showReportModal, setShowReportModal] = useState(false);
  const [selectedCandidate, setSelectedCandidate] = useState(null);
  const [extractedKeywords, setExtractedKeywords] = useState(null);
  const [isMatching, setIsMatching] = useState(false);
  const [uploadLoading, setUploadLoading] = useState(false);
  const [alert, setAlert] = useState({ show: false, message: '', type: 'info' });
  const [isDragging, setIsDragging] = useState(false);
  const [userResumes, setUserResumes] = useState([]);
  const [selectedResumeIds, setSelectedResumeIds] = useState([]);
  const [showExtractedKeywords, setShowExtractedKeywords] = useState(false);


  const showAlert = (message, type = 'info', duration = 6000) => {
      setAlert({ show: true, message, type });
      setTimeout(() => setAlert({ show: false, message: '', type: 'info' }), duration);
  };

  const fetchUserResumes = () => {
      apiClient.get('/resumes').then(response => {
          setUserResumes(response.data);
      }).catch(err => showAlert('Failed to fetch your resumes.', 'danger'));
  };

  useEffect(() => {
    fetchUserResumes();
  }, []);

  const handleResumeSelection = (resumeId) => {
    setSelectedResumeIds(prev =>
      prev.includes(resumeId)
        ? prev.filter(id => id !== resumeId)
        : [...prev, resumeId]
    );
  };
  
  const handleSelectAllResumes = (e) => {
    if (e.target.checked) {
      setSelectedResumeIds(userResumes.map(r => r.resume_id));
    } else {
      setSelectedResumeIds([]);
    }
  };

  // File Handlers
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
      const response = await apiClient.post('/upload_resumes', formData);
      const { processed_count, skipped_count, failed_count } = response.data;
      showAlert(`Upload complete! Processed: ${processed_count}, Skipped (duplicates): ${skipped_count}, Failed: ${failed_count}`, 'success', 8000);
      setSelectedFiles([]); 
      document.getElementById('file-input').value='';
      fetchUserResumes();
    } catch(err) { showAlert('Error uploading resumes.', 'danger');
    } finally { setUploadLoading(false);
    }
  };

  const handleFindTopMatches = async () => {
    if (!jdText.trim()) { showAlert('Please enter a Job Description.', 'warning'); return; }
    if (selectedResumeIds.length === 0) { showAlert('Please select at least one resume to match against.', 'warning'); return; }
    
    setIsMatching(true);
    setMatchedResults([]);
    setExtractedKeywords(null);
    setShowExtractedKeywords(false);
    
    try {
      // Step 1: Extract keywords silently
      const keywordsResponse = await apiClient.post('/extract-keywords', { job_description: jdText });
      const keywords = keywordsResponse.data;
      setExtractedKeywords(keywords);
      
      // Step 2: Find matches using selected resume IDs
      const payload = { keywords, top_k: topK, resume_ids: selectedResumeIds };
      const response = await apiClient.post('/match', payload);
      const results = response.data.results || [];
      setMatchedResults(results); 
      
      if (results.length > 0) {
        showAlert(`Found ${results.length} matches!`, 'success');
      } else {
        showAlert('ℹ️ No matching resumes found for the given criteria.', 'info');
      }
    } catch (err) {
      console.error("Matching Error:", err);
      showAlert('An error occurred while finding matches.', 'danger');
    } finally {
      setIsMatching(false);
    }
  };

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const handleDownloadResume = async (fileUrl, fileName) => {
    try {
      const response = await apiClient.get(fileUrl, {
        responseType: 'blob',
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', fileName);
      document.body.appendChild(link);
      link.click();
      link.parentNode.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Error downloading resume:', error);
      showAlert('Failed to download resume. You may need to log in again.', 'danger');
    }
  };

  const handleShowReport = (candidate) => {
    setSelectedCandidate(candidate);
    setShowReportModal(true);
  };
  const handleCloseReport = () => setShowReportModal(false);

  return (
    <div className="min-vh-100" style={{ background: 'linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%)' }}>
      {/* Header */}
      <div className="bg-white shadow-sm">
        <Container>
          <Row className="align-items-center py-3">
            <Col>
              <div className="d-flex align-items-center">
                <FiTarget size={32} className="text-primary me-3" />
                <div>
                  <h4 className="mb-0 fw-bold text-dark">Resume Matcher</h4>
                  <small className="text-muted">Find the perfect candidates instantly</small>
                </div>
              </div>
            </Col>
            <Col xs="auto">
              <div className="d-flex align-items-center">
                <span className="me-3 text-muted">Welcome, {user?.email}</span>
                <Button 
                  variant="outline-danger" 
                  size="sm" 
                  onClick={handleLogout}
                  className="d-flex align-items-center"
                >
                  <FiLogOut className="me-1" />
                  Logout
                </Button>
              </div>
            </Col>
          </Row>
        </Container>
      </div>

      <Container className="py-4">
        {/* Alerts */}
        <AnimatePresence>
          {alert.show && (
            <motion.div initial={{opacity:0,y:-20}} animate={{opacity:1,y:0}} exit={{opacity:0,y:-20}}>
              <Alert variant={alert.type} dismissible onClose={()=>setAlert({...alert, show:false})} className="shadow-sm mb-4 rounded-3">
                {alert.message}
              </Alert>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Progress Steps */}
        <Card className="mb-4 border-0 shadow-sm">
          <Card.Body className="py-4">
            <Row className="text-center">
              <Col md={4}>
                <div className="d-flex flex-column align-items-center">
                  <div className={`rounded-circle d-flex align-items-center justify-content-center mb-2 ${selectedFiles.length > 0 || userResumes.length > 0 ? 'bg-success text-white' : 'bg-light text-muted'}`} 
                       style={{ width: '60px', height: '60px' }}>
                    <FiUpload size={24} />
                  </div>
                  <h6 className="fw-semibold">1. Upload Resumes</h6>
                  <small className="text-muted">Add to your library</small>
                </div>
              </Col>
              <Col md={4}>
                <div className="d-flex flex-column align-items-center">
                  <div className={`rounded-circle d-flex align-items-center justify-content-center mb-2 ${jdText ? 'bg-success text-white' : 'bg-light text-muted'}`} 
                       style={{ width: '60px', height: '60px' }}>
                    <FiFileText size={24} />
                  </div>
                  <h6 className="fw-semibold">2. Enter Job Details</h6>
                  <small className="text-muted">Paste description & select resumes</small>
                </div>
              </Col>
              <Col md={4}>
                <div className="d-flex flex-column align-items-center">
                  <div className={`rounded-circle d-flex align-items-center justify-content-center mb-2 ${matchedResults.length > 0 ? 'bg-success text-white' : 'bg-light text-muted'}`} 
                       style={{ width: '60px', height: '60px' }}>
                    <FiTrendingUp size={24} />
                  </div>
                  <h6 className="fw-semibold">3. Find Matches</h6>
                  <small className="text-muted">Get top candidates</small>
                </div>
              </Col>
            </Row>
          </Card.Body>
        </Card>
        
        <Row className="justify-content-center">
          <Col lg={10} xl={8}>
            {/* Resume Upload Section */}
            <motion.div variants={fadeVariants} initial="hidden" animate="visible">
              <Card className="mb-4 border-0 shadow-sm">
                <Card.Header className="bg-white border-bottom-0 py-3">
                  <div className="d-flex align-items-center">
                    <FiUpload className="text-primary me-2" size={20} />
                    <h5 className="mb-0 fw-semibold">Upload Resumes</h5>
                  </div>
                </Card.Header>
                <Card.Body>
                  <div
                    className={`border-2 border-dashed rounded-3 p-4 text-center transition-all ${isDragging ? 'border-primary bg-primary bg-opacity-10' : 'border-light-grey'}`}
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={handleDrop}
                    onClick={() => document.getElementById('file-input').click()}
                    style={{ cursor: 'pointer', minHeight: '140px', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}
                  >
                    <input 
                      id="file-input" 
                      type="file" 
                      multiple 
                      accept=".pdf,.docx,.txt" 
                      onChange={(e)=>handleFileChange(e.target.files)} 
                      style={{display:'none'}}
                    />
                    <FiUpload size={32} className="text-primary mb-2" />
                    <h6 className="fw-semibold text-dark">Drop files here or click to browse</h6>
                    <p className="text-muted mb-0">Support for PDF, DOCX, TXT files</p>
                  </div>

                  {selectedFiles.length > 0 && (
                    <div className="mt-3">
                      <h6 className="fw-semibold mb-2">Selected Files ({selectedFiles.length})</h6>
                      <div className="bg-light rounded-3 p-3" style={{maxHeight:'120px', overflowY:'auto'}}>
                        {selectedFiles.slice(0,3).map((file,i)=>(
                          <div key={i} className="d-flex justify-content-between align-items-center py-1">
                            <span className="small">{file.name}</span>
                            <Badge bg="info" className="small">{(file.size/1024).toFixed(1)} KB</Badge>
                          </div>
                        ))}
                        {selectedFiles.length > 3 && (
                          <div className="text-muted small">+ {selectedFiles.length-3} more files</div>
                        )}
                      </div>
                    </div>
                  )}

                  <div className="d-grid mt-3">
                    <Button 
                      variant="primary" 
                      onClick={uploadResumes} 
                      disabled={uploadLoading || selectedFiles.length===0} 
                      size="lg"
                      className="fw-semibold"
                    >
                      {uploadLoading ? (
                        <><Spinner size="sm" className="me-2"/>Uploading...</>
                      ) : (
                        <>Upload {selectedFiles.length} File(s)</>
                      )}
                    </Button>
                  </div>

                  {userResumes.length > 0 && (
                    <div className="mt-3 p-3 bg-success bg-opacity-10 rounded-3">
                      <div className="d-flex align-items-center">
                        <FiCheckCircle className="text-success me-2" />
                        <span className="text-success fw-semibold">
                          {userResumes.length} resume(s) available in your library
                        </span>
                      </div>
                    </div>
                  )}
                </Card.Body>
              </Card>
            </motion.div>

            {/* Job Description & Matching Section */}
            <motion.div variants={fadeVariants} initial="hidden" animate="visible">
              <Card className="mb-4 border-0 shadow-sm">
                <Card.Header className="bg-white border-bottom-0 py-3">
                  <div className="d-flex align-items-center">
                    <FiFileText className="text-primary me-2" size={20} />
                    <h5 className="mb-0 fw-semibold">Job Description & Matching</h5>
                  </div>
                </Card.Header>
                <Card.Body>
                  <Form.Group className="mb-3">
                    <Form.Label className="fw-semibold">Job Description</Form.Label>
                    <Form.Control 
                      as="textarea" 
                      rows={8} 
                      value={jdText} 
                      onChange={e=>setJdText(e.target.value)} 
                      placeholder="Paste the job description here..."
                      className="rounded-3"
                    />
                  </Form.Group>
                  
                  <Form.Group className="mb-3">
                    <Form.Label className="fw-semibold">Match Against</Form.Label>
                    {userResumes.length > 0 ? (
                        <div className="border rounded-3 p-3" style={{maxHeight: '200px', overflowY: 'auto'}}>
                            <Form.Check
                                type="checkbox"
                                id="select-all-resumes"
                                label={`Select All (${selectedResumeIds.length}/${userResumes.length})`}
                                checked={selectedResumeIds.length === userResumes.length && userResumes.length > 0}
                                onChange={handleSelectAllResumes}
                                className="fw-semibold mb-2 border-bottom pb-2"
                            />
                            {userResumes.map(resume => (
                                <Form.Check
                                    key={resume.resume_id}
                                    type="checkbox"
                                    id={`resume-${resume.resume_id}`}
                                    label={resume.candidate_name || resume.file_name}
                                    checked={selectedResumeIds.includes(resume.resume_id)}
                                    onChange={() => handleResumeSelection(resume.resume_id)}
                                    className="my-1"
                                />
                            ))}
                        </div>
                    ) : (
                        <div className="text-center py-3 text-muted border rounded-3">
                            <FiClock size={24} className="mb-2" />
                            <p className="mb-0 small">No resumes in your library to select.</p>
                        </div>
                    )}
                  </Form.Group>

                  <Row className="align-items-end">
                    <Col xs={12} sm={5} className="mb-3 mb-sm-0">
                        <Form.Group>
                            <Form.Label className="fw-semibold small">Number of Top Matches</Form.Label>
                            <Form.Control 
                                type="number" 
                                value={topK} 
                                min={1} 
                                max={50} 
                                onChange={e => setTopK(parseInt(e.target.value) || 1)}
                                className="rounded-3"
                            />
                        </Form.Group>
                    </Col>
                    <Col xs={12} sm={7}>
                        <div className="d-grid">
                            <Button 
                                variant="success" 
                                onClick={handleFindTopMatches} 
                                disabled={isMatching || !jdText.trim() || selectedResumeIds.length === 0} 
                                size="lg"
                                className="fw-semibold"
                            >
                                {isMatching ? (
                                    <><Spinner size="sm" className="me-2"/>Searching...</>
                                ) : (
                                    <><FiSearch className="me-2"/>Find Top Matches</>
                                )}
                            </Button>
                        </div>
                    </Col>
                  </Row>
                </Card.Body>
              </Card>
            </motion.div>
            
            {/* Extracted Keywords Trigger & Display */}
            {extractedKeywords && (
              <div className="text-center mb-3">
                <Button variant="link" onClick={() => setShowExtractedKeywords(!showExtractedKeywords)}>
                  {showExtractedKeywords ? <FiEyeOff className="me-1" /> : <FiEye className="me-1" />}
                  {showExtractedKeywords ? 'Hide' : 'Show'} Extracted Keywords
                </Button>
              </div>
            )}

            <AnimatePresence>
              {showExtractedKeywords && extractedKeywords && (
                <motion.div variants={fadeVariants} initial="hidden" animate="visible" exit="hidden">
                  <Card className="mb-4 border-0 shadow-sm">
                    <Card.Header className="bg-success bg-opacity-10 border-bottom-0 py-3">
                      <div className="d-flex align-items-center">
                        <FiCheckCircle className="text-success me-2" size={20} />
                        <h5 className="mb-0 fw-semibold text-success">Keywords Extracted</h5>
                      </div>
                    </Card.Header>
                    <Card.Body>
                      <Row>
                        <Col md={6}>
                          <h6 className="fw-semibold text-primary mb-2">Required Keywords</h6>
                          {extractedKeywords.required_keywords && Object.entries(extractedKeywords.required_keywords).map(([cat,list])=>list.length>0&&(
                            <div key={cat} className="mb-2">
                              <small className="fw-semibold text-dark d-block">{cat.replace(/_/g,' ').toUpperCase()}</small>
                              <div className="d-flex flex-wrap gap-1">
                                {list.map(keyword => (
                                  <Badge key={keyword} bg="primary" className="small fw-normal">{keyword}</Badge>
                                ))}
                              </div>
                            </div>
                          ))}
                        </Col>
                        <Col md={6}>
                          <h6 className="fw-semibold text-secondary mb-2">Preferred Keywords</h6>
                          {extractedKeywords.preferred_keywords && Object.entries(extractedKeywords.preferred_keywords).map(([cat,list])=>list.length>0&&(
                            <div key={cat} className="mb-2">
                              <small className="fw-semibold text-dark d-block">{cat.replace(/_/g,' ').toUpperCase()}</small>
                              <div className="d-flex flex-wrap gap-1">
                                {list.map(keyword => (
                                  <Badge key={keyword} bg="secondary" className="small fw-normal">{keyword}</Badge>
                                ))}
                              </div>
                            </div>
                          ))}
                        </Col>
                      </Row>
                    </Card.Body>
                  </Card>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Match Results */}
            {matchedResults.length > 0 && (
              <motion.div 
                variants={staggerContainer}
                initial="hidden" 
                animate="visible"
              >
                <Card className="border-0 shadow-sm">
                  <Card.Header className="bg-success bg-opacity-10 border-bottom-0 py-3">
                    <div className="d-flex align-items-center">
                      <FiAward className="text-success me-2" size={20} />
                      <h5 className="mb-0 fw-semibold text-success">Top {matchedResults.length} Matches</h5>
                    </div>
                  </Card.Header>
                  <Card.Body className="p-0">
                    <div style={{maxHeight: '500px', overflowY: 'auto'}}>
                      {matchedResults.map((result, idx) => (
                        <motion.div 
                          key={result.resume_id} 
                          variants={slideInVariants}
                          className="border-bottom p-4 hover-bg-light"
                        >
                          <Row className="align-items-center">
                            <Col md={8}>
                              <div className="d-flex align-items-start">
                                <div className="me-3">
                                  <div 
                                    className="rounded-circle bg-primary text-white d-flex align-items-center justify-content-center fw-bold"
                                    style={{ width: '40px', height: '40px', fontSize: '14px' }}
                                  >
                                    #{idx + 1}
                                  </div>
                                </div>
                                <div className="flex-grow-1">
                                  <h6 className="fw-bold text-dark mb-1">{result.name}</h6>
                                  <p className="text-muted small mb-1">{result.current_title || 'No title specified'}</p>
                                  <p className="text-muted small mb-2 fst-italic">
                                      <FiFileText size={12} className="me-1" />
                                      {result.file_name}
                                  </p>
                                  <p className="text-dark small mb-2 lh-sm" style={{
                                    display: '-webkit-box',
                                    WebkitLineClamp: 2,
                                    WebkitBoxOrient: 'vertical',
                                    overflow: 'hidden'
                                  }}>
                                    {result.summary || 'No summary available.'}
                                  </p>
                                  <div className="d-flex gap-2">
                                    <Button 
                                      variant="outline-primary" 
                                      size="sm" 
                                      onClick={() => handleDownloadResume(result.file_url, result.file_name)}
                                      className="d-flex align-items-center"
                                    >
                                      <FiDownload size={14} className="me-1" />
                                      Download
                                    </Button>
                                    <Button 
                                      variant="outline-info" 
                                      size="sm" 
                                      onClick={() => handleShowReport(result)}
                                      className="d-flex align-items-center"
                                    >
                                      <FiEye size={14} className="me-1" />
                                      Report
                                    </Button>
                                  </div>
                                </div>
                              </div>
                            </Col>
                            <Col md={4} className="text-center">
                              <div className="position-relative d-inline-block">
                                <svg width="80" height="80" viewBox="0 0 36 36" className="circular-chart">
                                  <path className="circle-bg" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" 
                                        fill="none" stroke="#e6e6e6" strokeWidth="2"/>
                                  <path className="circle" strokeDasharray={`${Math.round(result.score * 100)}, 100`} 
                                        d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                                        fill="none" stroke={result.score > 0.7 ? '#28a745' : result.score > 0.5 ? '#ffc107' : '#dc3545'} 
                                        strokeWidth="2" strokeLinecap="round"/>
                                </svg>
                                <div className="position-absolute top-50 start-50 translate-middle">
                                  <div className="fw-bold text-dark" style={{fontSize: '16px'}}>
                                    {Math.round(result.score * 100)}%
                                  </div>
                                  <div className="small text-muted">Match</div>
                                </div>
                              </div>
                            </Col>
                          </Row>
                        </motion.div>
                      ))}
                    </div>
                  </Card.Body>
                </Card>
              </motion.div>
            )}
          </Col>
        </Row>
      </Container>

      {/* Detailed Report Modal */}
      {selectedCandidate && (
        <Modal show={showReportModal} onHide={handleCloseReport} size="lg" centered>
          <Modal.Header closeButton className="bg-light">
            <Modal.Title className="fw-bold">
              Detailed Report: {selectedCandidate.name}
            </Modal.Title>
          </Modal.Header>
          <Modal.Body>
            <div className="mb-3">
              <p className="text-muted">
                This report shows the keywords from the job description and indicates which ones were found in the candidate's resume. 
                The score is calculated based only on the "Scoring Keywords" section.
              </p>
              <div className="d-flex align-items-center gap-3">
                <div className="d-flex align-items-center">
                  <Badge bg="success" className="me-2">Matched</Badge>
                  <span className="small text-muted">Found in resume</span>
                </div>
                <div className="d-flex align-items-center">
                  <Badge bg="secondary" className="me-2">Not Found</Badge>
                  <span className="small text-muted">Missing from resume</span>
                </div>
              </div>
            </div>
            
            <div className="border-top pt-3">
              <ReportSection 
                title="🎯 Scoring Keywords"
                keywordsData={selectedCandidate.report_details.scoring_keywords} 
              />
              
              <div className="border-top pt-3 mt-3">
                <ReportSection 
                  title="📋 Additional Keywords (for context)"
                  keywordsData={selectedCandidate.report_details.additional_keywords}
                />
              </div>
            </div>
          </Modal.Body>
          <Modal.Footer className="bg-light">
            <Button variant="secondary" onClick={handleCloseReport}>
              Close Report
            </Button>
            <Button 
              variant="primary" 
              onClick={() => handleDownloadResume(selectedCandidate.file_url, selectedCandidate.file_name)}
            >
              <FiDownload className="me-1" />
              Download Resume
            </Button>
          </Modal.Footer>
        </Modal>
      )}

      <style jsx>{`
        .hover-bg-light:hover {
          background-color: #f8f9fa !important;
          transition: background-color 0.2s ease;
        }
        
        .circular-chart {
          transform: rotate(-90deg);
        }
        
        .custom-checkbox .form-check-input:checked {
          background-color: #0d6efd;
          border-color: #0d6efd;
        }
        
        .transition-all {
          transition: all 0.3s ease;
        }
      `}</style>
    </div>
  );
}

// Main App component with routing
function App() {
    return (
        <AuthProvider>
            <Router>
                <Routes>
                    <Route path="/login" element={<LoginPage />} />
                    <Route 
                        path="/*" 
                        element={
                            <ProtectedRoute>
                                <MainApp />
                            </ProtectedRoute>
                        } 
                    />
                </Routes>
            </Router>
        </AuthProvider>
    );
}

export default App;