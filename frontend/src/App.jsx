import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Shell from './components/layout/Shell'
import LiveRace from './views/LiveRace'
import RaceResults from './views/RaceResults'
import HorseProfile from './views/HorseProfile'
import RaceCardBuilder from './views/RaceCardBuilder'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 0,
    },
  },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Shell />}>
            <Route index element={<Navigate to="/live" replace />} />
            <Route path="/live" element={<LiveRace />} />
            <Route path="/results" element={<RaceResults />} />
            <Route path="/horses" element={<HorseProfile />} />
            <Route path="/horses/:epc" element={<HorseProfile />} />
            <Route path="/builder" element={<RaceCardBuilder />} />
            <Route path="*" element={<Navigate to="/live" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}