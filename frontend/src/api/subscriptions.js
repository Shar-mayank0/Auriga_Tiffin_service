import client from './client.js'

export const subscribe = (planId, startDate) => client.post('/subscriptions/', { plan_id: planId, start_date: startDate })
export const getMySubscription = () => client.get('/subscriptions/mine/')
