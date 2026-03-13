import { useState, useCallback } from 'react'

export function useApi(baseUrl, apiKey) {
  const [loading, setLoading] = useState(false)

  const call = useCallback(async (path, method = 'GET', body = null) => {
    const url = baseUrl.replace(/\/+$/, '') + path
    const opts = {
      method,
      headers: {
        'Content-Type': 'application/json',
        'X-Api-Key': apiKey,
      },
    }
    if (body) opts.body = JSON.stringify(body)
    const res = await fetch(url, opts)
    const data = await res.json()
    if (!res.ok) throw new Error(data.detail || JSON.stringify(data))
    return data
  }, [baseUrl, apiKey])

  const callWithLoading = useCallback(async (path, method = 'GET', body = null) => {
    setLoading(true)
    try {
      return await call(path, method, body)
    } finally {
      setLoading(false)
    }
  }, [call])

  return { call, callWithLoading, loading }
}
