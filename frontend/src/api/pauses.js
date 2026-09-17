import client from './client.js'

export const createPause = (data) => client.post('/pauses/', data)
export const resumePause = (pauseId, resumeDate) => client.patch(`/pauses/${pauseId}/resume/`, resumeDate ? { resume_date: resumeDate } : {})
export const getMyPauses = () => client.get('/pauses/')
