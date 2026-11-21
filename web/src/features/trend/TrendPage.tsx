import { useState } from 'react';
import { TrendChart } from './components/TrendChart';
import { useTrend } from './data/useTrend';
import type { TrendBucket } from './model';

export function TrendPage() {
  const [bucket, setBucket] = useState<TrendBucket>('hour');
  const { points, isLoading, isError } = useTrend(bucket);
  return <TrendChart points={points} bucket={bucket} onBucketChange={setBucket} isLoading={isLoading} isError={isError} />;
}
