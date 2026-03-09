/**
 * WorkflowIcon - Custom SVG icon for workflows (chaîne d'actions).
 * Theme-adaptive color; single-color for a clean, "plus fin" look.
 * SVG source: workflows-svgrepo-com.svg (paths simplified to currentColor).
 */

import type { CSSProperties, FC, ReactElement } from 'react';
import { useTheme } from '../../contexts/ThemeContext';

export interface WorkflowIconProps {
  /** Size in pixels (width and height). Default 24. */
  size?: number;
  /** For compatibility with iconHelpers: fontSize sets size. */
  fontSize?: number;
  /** Optional className. */
  className?: string;
  /** Optional style (merged with size). */
  style?: CSSProperties;
  /** Accessible label. */
  'aria-label'?: string;
}

/** Workflow SVG paths (viewBox 0 0 24 24) — all use currentColor for theme. */
const WorkflowSvg: FC<{ size: number; color: string; ariaLabel?: string }> = ({
  size,
  color,
  ariaLabel,
}) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    xmlns="http://www.w3.org/2000/svg"
    role="img"
    aria-label={ariaLabel}
    style={{ display: 'block', flexShrink: 0 }}
  >
    <path fill={color} fillRule="evenodd" d="M19.5,20.06h-.7v-1.5h.7a.76.76,0,0,0,.75-.75V13.5a.76.76,0,0,0-.75-.75H15.89v-1.5H19.5a2.25,2.25,0,0,1,2.25,2.25v4.31A2.25,2.25,0,0,1,19.5,20.06Z" />
    <path fill={color} d="M11.55,20.06H6.65v-1.5h4.9Z" />
    <path fill={color} fillRule="evenodd" d="M8.12,12.75H4.5A2.25,2.25,0,0,1,2.25,10.5V6.19A2.25,2.25,0,0,1,4.5,3.94h1v1.5h-1a.75.75,0,0,0-.75.75V10.5a.76.76,0,0,0,.75.75H8.12Z" />
    <path fill={color} d="M17.3,5.44H11.82V3.94H17.3Z" />
    <path fill={color} d="M8.63,3.94V2.44h-3A1.13,1.13,0,0,0,4.5,3.56V5.81A1.13,1.13,0,0,0,5.63,6.94h3V5.44H6V3.94Z" />
    <path fill={color} fillRule="evenodd" d="M12.75,3.56V5.81a1.13,1.13,0,0,1-1.12,1.13h-3V5.44h2.62V3.94H8.63V2.44h3A1.12,1.12,0,0,1,12.75,3.56Z" />
    <path fill={color} d="M19.31,7.13a2.44,2.44,0,1,1,2.44-2.44A2.45,2.45,0,0,1,19.31,7.13Zm0-3.38a.94.94,0,1,0,.94.94A.94.94,0,0,0,19.31,3.75Z" />
    <path fill={color} d="M4.69,21.75a2.44,2.44,0,1,1,2.43-2.44A2.44,2.44,0,0,1,4.69,21.75Zm0-3.38a.94.94,0,1,0,.93.94A.94.94,0,0,0,4.69,18.37Z" />
    <path fill={color} d="M15.36,18.57v-1.5h-3a1.13,1.13,0,0,0-1.12,1.13v2.25a1.12,1.12,0,0,0,1.12,1.12h3v-1.5H12.74v-1.5Z" />
    <path fill={color} fillRule="evenodd" d="M19.49,18.2v2.25a1.13,1.13,0,0,1-1.13,1.12h-3v-1.5H18v-1.5H15.36v-1.5h3A1.14,1.14,0,0,1,19.49,18.2Z" />
    <path fill={color} d="M12,11.25V9.75H9a1.13,1.13,0,0,0-1.13,1.12v2.25A1.13,1.13,0,0,0,9,14.25h3v-1.5H9.37v-1.5Z" />
    <path fill={color} fillRule="evenodd" d="M16.12,10.87v2.25A1.13,1.13,0,0,1,15,14.25H12v-1.5h2.62v-1.5H12V9.75h3A1.12,1.12,0,0,1,16.12,10.87Z" />
  </svg>
);

/** Workflow icon with theme-adaptive color (violet in light, lighter in dark). */
export function WorkflowIcon({
  size: sizeProp,
  fontSize,
  className,
  style,
  'aria-label': ariaLabel = 'Workflow',
}: WorkflowIconProps): ReactElement {
  const { effectiveMode } = useTheme();
  const isDark = effectiveMode === 'dark';
  const color = isDark ? '#b8a0d4' : '#722ed1';
  const size = fontSize ?? sizeProp ?? 24;

  return (
    <span className={className} style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', ...style }}>
      <WorkflowSvg size={size} color={color} ariaLabel={ariaLabel} />
    </span>
  );
}
