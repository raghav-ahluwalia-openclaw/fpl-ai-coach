import React from 'react';

interface SkeletonBlockProps {
  className?: string;
  count?: number;
  height?: string;
  width?: string;
}

export const SkeletonBlock: React.FC<SkeletonBlockProps> = ({ 
  className = '', 
  count = 1,
  height = '1rem',
  width = '100%'
}) => {
  return (
    <div className={`space-y-2 ${className}`}>
      {Array.from({ length: count }).map((_, i) => (
        <div 
          key={i} 
          className="bg-border/20 rounded-md animate-pulse"
          style={{ height, width }}
        />
      ))}
    </div>
  );
};
