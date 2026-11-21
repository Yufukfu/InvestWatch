import { useGetStatsTrendQuery } from '../../../api/generated';
import type { TrendBucket, TrendPoint } from '../model';

const NO_POINTS: TrendPoint[] = [];

export function useTrend(bucket: TrendBucket) {
  const { currentData, isFetching, isError } = useGetStatsTrendQuery({ bucket });
  return {
    points: currentData?.points ?? NO_POINTS,
    // Loading until the response for the *current* bucket has arrived (no stale hourly data under "Dzień").
    isLoading: isFetching && !currentData,
    isError,
  };
}
