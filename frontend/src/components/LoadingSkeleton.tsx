import { Box, Skeleton } from '@mui/material';

interface LoadingSkeletonProps {
  variant?: 'text' | 'rectangular' | 'circular';
  count?: number;
  height?: number;
}

const LoadingSkeleton = ({ variant = 'rectangular', count = 3, height = 60 }: LoadingSkeletonProps) => {
  return (
    <Box>
      {Array.from({ length: count }).map((_, index) => (
        <Skeleton
          key={index}
          variant={variant}
          height={height}
          sx={{ mb: 2 }}
          animation="wave"
        />
      ))}
    </Box>
  );
};

export default LoadingSkeleton;
