import { useState, useRef } from 'react'
import { Search, Loader2, Mic, MicOff } from 'lucide-react'
import axios from 'axios'
import './SearchSection.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function SearchSection({ onSearch, isSearching, setIsSearching }) {
  const [query, setQuery] = useState('')
  const [topK, setTopK] = useState(5)
  const [isListening, setIsListening] = useState(false)
  const [speechSupported, setSpeechSupported] = useState(false)
  const recognitionRef = useRef(null)

  if (!recognitionRef.current && typeof window !== 'undefined') {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (SR) {
      const rec = new SR()
      rec.continuous = false
      rec.interimResults = true
      rec.lang = 'en-US'
      rec.onresult = (event) => {
        let finalText = ''
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const t = event.results[i][0].transcript
          if (event.results[i].isFinal) finalText += t
        }
        const text = finalText || event.results[0][0].transcript || ''
        if (text) setQuery((prev) => text)
      }
      rec.onend = () => {
        setIsListening(false)
      }
      recognitionRef.current = rec
      setSpeechSupported(true)
    } else {
      setSpeechSupported(false)
    }
  }

  const handleSearch = async (e) => {
    e.preventDefault()
    
    if (!query.trim()) {
      return
    }

    setIsSearching(true)
    if (isListening && recognitionRef.current) {
      try { recognitionRef.current.stop() } catch {}
      setIsListening(false)
    }
    try {
      const token = localStorage.getItem('lexivion_token')
      if (!token) {
        onSearch({ answer: '', sections: [], context: [], error: 'Please sign in to search.' })
        return
      }
      const response = await axios.post(
        `${API_URL}/api/search`,
        {
          query: query.trim(),
          top_k: topK,
        },
        {
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
          },
        }
      )

      onSearch(response.data)
    } catch (error) {
      console.error('Search error:', error)
      onSearch({
        answer: '',
        sections: [],
        context: [],
        error: error.response?.data?.error || 'Search failed. Please try again.',
      })
    } finally {
      setIsSearching(false)
    }
  }

  const toggleListening = () => {
    if (!speechSupported || !recognitionRef.current || isSearching) return
    if (isListening) {
      try { recognitionRef.current.stop() } catch {}
      setIsListening(false)
    } else {
      try {
        setIsListening(true)
        recognitionRef.current.start()
      } catch {
        setIsListening(false)
      }
    }
  }

  return (
    <div className="search-section">
      <div className="section-header">
        <Search size={24} />
        <h2>Search Documents</h2>
      </div>

      <form onSubmit={handleSearch} className="search-form">
        <div className="search-input-group">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={speechSupported ? "Type or use voice…" : "Enter your search query..."}
            className="search-input"
            disabled={isSearching}
          />
          <button
            type="button"
            className={`mic-btn ${isListening ? 'listening' : ''}`}
            onClick={toggleListening}
            disabled={!speechSupported || isSearching}
            aria-label={isListening ? 'Stop listening' : 'Start voice input'}
          >
            {isListening ? <MicOff size={20} /> : <Mic size={20} />}
          </button>
          <button
            type="submit"
            className="search-btn"
            disabled={!query.trim() || isSearching}
          >
            {isSearching ? (
              <Loader2 size={20} className="spinner" />
            ) : (
              <Search size={20} />
            )}
          </button>
        </div>

        <div className="search-options">
          <label>
            Number of results:
            <input
              type="number"
              min="1"
              max="20"
              value={topK}
              onChange={(e) => setTopK(parseInt(e.target.value) || 5)}
              className="top-k-input"
              disabled={isSearching}
            />
          </label>
        </div>
      </form>
    </div>
  )
}

export default SearchSection

