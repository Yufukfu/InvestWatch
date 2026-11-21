import { setupWorker } from 'msw/browser';
import { config } from '../config';
import { handlers } from './handlers';

export const worker = setupWorker(...handlers(config.apiBaseUrl));
