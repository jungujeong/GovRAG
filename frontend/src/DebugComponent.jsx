import React from 'react'

function DebugComponent() {
  console.log('DebugComponent mounting')
  return (
    <div style={{ padding: '20px', fontSize: '18px' }}>
      <h1>Debug Component is Working</h1>
      <p>If you see this, React is loading properly.</p>
      <p>Time: {new Date().toISOString()}</p>
    </div>
  )
}

export default DebugComponent