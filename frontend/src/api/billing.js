import client from './client.js'

export const getMyBills = () => client.get('/billing/')
