import express from 'express';
import morgan from 'morgan';
import session from 'express-session';
import path from 'path';
import { ensureEnvReady, APP_CONFIG } from './config';
import './db';
import authRouter from './routes/auth';
import featuresRouter from './routes/features';
import botSyncRouter from './routes/botSync';

ensureEnvReady();

const app = express();
app.set('trust proxy', true);
app.use(express.json({ limit: '5mb' }));
app.use(morgan('dev'));
app.use(
  session({
    secret: APP_CONFIG.sessionSecret,
    resave: false,
    saveUninitialized: false,
  }),
);

app.use('/uploads', express.static(path.join(APP_CONFIG.uploadsDir)));
app.use(express.static(path.join(process.cwd())));

app.use('/auth', authRouter);
app.use('/api', featuresRouter);
app.use('/bot-sync', botSyncRouter);

app.use((err: Error, _req: express.Request, res: express.Response, _next: express.NextFunction) => {
  console.error(err);
  res.status(500).json({ message: err.message || 'Internal server error' });
});

app.listen(APP_CONFIG.port, () => {
  console.log(`Memento Mori API running on port ${APP_CONFIG.port}`);
});
