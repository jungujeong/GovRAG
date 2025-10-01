import AppMediumClean from './AppMediumClean'
import AppMinimal from './AppMinimal'
import DebugComponent from './DebugComponent'

function App() {
  console.log('App component loading...')

  // Testing modes
  const USE_MINIMAL = false  // Set to true to use minimal version
  const DEBUG_MODE = false

  if (DEBUG_MODE) {
    return <DebugComponent />
  }

  if (USE_MINIMAL) {
    console.log('Using minimal app for testing')
    return <AppMinimal />
  }

  try {
    return <AppMediumClean />
  } catch (error) {
    console.error('Error loading AppMediumClean:', error)
    return (
      <div style={{ padding: '20px', color: 'red' }}>
        <h1>Error loading application</h1>
        <p>{error.message}</p>
      </div>
    )
  }
}

export default App

