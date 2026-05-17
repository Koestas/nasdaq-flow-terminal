import { BrowserRouter, Routes, Route } from 'react-router-dom'
import TopBar from './components/TopBar'
import Sidebar from './components/Sidebar'
import ErrorBoundary from './components/ErrorBoundary'
import Overview from './pages/Overview'
import Wave from './pages/Wave'
import Gex from './pages/Gex'
import TopFlow from './pages/TopFlow'
import Unusual from './pages/Unusual'
import RawChain from './pages/RawChain'
import Leadership from './pages/Leadership'
import Structure from './pages/Structure'
import News from './pages/News'
import Tape from './pages/Tape'
import Replay from './pages/Replay'
import Journal from './pages/Journal'
import Diagnostics from './pages/Diagnostics'
import ICT from './pages/ICT'

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-terminal-bg">
        <TopBar />
        <Sidebar />
        <main className="pt-12 pl-44 min-h-screen transition-all duration-200">
          <div className="p-4 max-w-[1600px] mx-auto">
            <ErrorBoundary>
              <Routes>
                <Route path="/" element={<Overview />} />
                <Route path="/wave" element={<Wave />} />
                <Route path="/gex" element={<Gex />} />
                <Route path="/top-flow" element={<TopFlow />} />
                <Route path="/unusual" element={<Unusual />} />
                <Route path="/raw-chain" element={<RawChain />} />
                <Route path="/leadership" element={<Leadership />} />
                <Route path="/structure" element={<Structure />} />
                <Route path="/news" element={<News />} />
                <Route path="/tape" element={<Tape />} />
                <Route path="/replay" element={<Replay />} />
                <Route path="/journal" element={<Journal />} />
                <Route path="/diagnostics" element={<Diagnostics />} />
                <Route path="/ict" element={<ICT />} />
                <Route path="*" element={<Overview />} />
              </Routes>
            </ErrorBoundary>
          </div>
        </main>
      </div>
    </BrowserRouter>
  )
}
