import client from './client.js'

export const listPlans = () => client.get('/plans/')
