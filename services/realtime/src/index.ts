if (process.env.NEVOLIUM_ENV === 'production') throw new Error('Realtime collaboration is not integrated; production activation is blocked until D12')

import { Server } from '@hocuspocus/server'

const port = Number(process.env.PORT ?? 1234)

const server = new Server({
  port,
  address: '0.0.0.0',
  name: 'Nevolium Realtime',
  debounce: 1500,
  maxDebounce: 5000,
  async onConnect({ documentName }) {
    console.info(`[nevolium-realtime] connected document=${documentName}`)
  },
  async onStoreDocument({ documentName }) {
    // Block 1 replaces this log with canonical snapshot/event persistence through Nevolium Core.
    console.info(`[nevolium-realtime] store requested document=${documentName}`)
  },
})

server.listen().then(() => {
  console.info(`[nevolium-realtime] listening on ${port}`)
})
