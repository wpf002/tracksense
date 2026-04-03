import { create } from 'zustand'

const useRaceStore = create((set) => ({
  status: 'idle',
  horses: [],
  lastEvent: null,
  lastEventTime: null,
  connected: false,

  setStatus: (status) => set({ status }),
  setHorses: (horses) => set({ horses }),
  setLastEvent: (event) => set({ lastEvent: event, lastEventTime: Date.now() }),
  setConnected: (connected) => set({ connected }),
}))

export default useRaceStore