import 'express-session';
import type { SessionUser } from '../middleware/auth';

declare module 'express-session' {
  interface SessionData {
    user?: SessionUser;
  }
}
