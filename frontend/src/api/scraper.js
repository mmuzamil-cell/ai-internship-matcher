import client from './client'

/**
 * Get the list of available scraping sources.
 */
export const getScraperSources = async () => {
  const res = await client.get('/scraper/sources')
  return res.data
}

/**
 * Trigger scraping from selected sources.
 * @param {Object} params
 * @param {string} params.keyword - Search keyword
 * @param {string} params.sources - Comma-separated source keys or 'all'
 * @param {number} params.limit - Max results per source
 */
export const scrapeInternships = async ({ keyword = 'internship', sources = 'all', limit = 15 } = {}) => {
  const res = await client.post('/scraper/scrape', null, {
    params: { keyword, sources, limit },
  })
  return res.data
}

/**
 * Get scraping statistics.
 */
export const getScraperStatus = async () => {
  const res = await client.get('/scraper/status')
  return res.data
}
