import { createRoot } from 'react-dom/client'
/* Order matters: legacy first, token layer second.
   theme.css deliberately wins the six colliding tokens (--border, --radius,
   --radius-lg, --radius-xl, --font-display, --font-data) so unmigrated screens
   pick up the new border colour and radii immediately, instead of drifting
   apart from migrated ones for the length of the migration. */
import './index.css'
import './theme.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(<App />)
