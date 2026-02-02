/**
 * Cron expression helper utilities (Story 11.8).
 *
 * Provides functions to:
 * - Generate human-readable descriptions for cron expressions
 * - Common cron presets with labels
 */

/**
 * Generate human-readable description for a cron expression.
 *
 * @param expression - Cron expression (5 fields: minute hour day month day_of_week)
 * @returns Human-readable description in French
 */
export function describeCronExpression(expression: string): string {
  try {
    const parts = expression.trim().split(/\s+/);

    if (parts.length !== 5) {
      return expression; // Return raw if not 5 fields
    }

    const [minute, hour, day, month, dow] = parts;

    // Common exact patterns (Story 11.8, AC8 - description lisible)
    if (expression === '0 2 * * *') return 'Tous les jours à 2h00';
    if (expression === '0 14 * * 1') return 'Tous les lundis à 14h00';
    if (expression === '0 18 * * 5') return 'Tous les vendredis à 18h00';
    if (expression === '0 0 1 * *') return 'Le 1er de chaque mois à minuit';
    if (expression === '*/15 * * * *') return 'Toutes les 15 minutes';
    if (expression === '0 2 * * 1-5') return 'Tous les jours ouvrables à 2h00';
    if (expression === '0 9,17 * * *') return 'Tous les jours à 9h00 et 17h00';
    if (expression === '0 9,17 * * 1-5') return 'Jours ouvrables à 9h00 et 17h00';

    // Build description dynamically
    let description = '';

    // Handle day of week patterns
    if (dow !== '*') {
      const dayNames: Record<string, string> = {
        '0': 'dimanches',
        '1': 'lundis',
        '2': 'mardis',
        '3': 'mercredis',
        '4': 'jeudis',
        '5': 'vendredis',
        '6': 'samedis',
        '1-5': 'jours ouvrables',
        '0,6': 'week-ends',
        '0-6': 'jours',
      };
      const dayName = dayNames[dow];
      if (dayName) {
        description += `Tous les ${dayName}`;
      } else {
        // Handle single day number
        const singleDayNames: Record<string, string> = {
          '0': 'dimanches',
          '1': 'lundis',
          '2': 'mardis',
          '3': 'mercredis',
          '4': 'jeudis',
          '5': 'vendredis',
          '6': 'samedis',
        };
        if (singleDayNames[dow]) {
          description += `Tous les ${singleDayNames[dow]}`;
        } else {
          description += `Jours ${dow}`;
        }
      }
    } else if (day !== '*') {
      // Handle day of month patterns
      if (day === '1') {
        description += 'Le 1er de chaque mois';
      } else if (day === 'L') {
        description += 'Le dernier jour de chaque mois';
      } else {
        description += `Le ${day} de chaque mois`;
      }
    } else {
      description += 'Tous les jours';
    }

    // Handle time patterns
    if (minute.startsWith('*/')) {
      const interval = minute.substring(2);
      description = `Toutes les ${interval} minutes`;
    } else if (hour.startsWith('*/')) {
      const interval = hour.substring(2);
      description += ` toutes les ${interval} heures`;
    } else if (hour.includes(',')) {
      const hours = hour
        .split(',')
        .map((h) => `${h}h00`)
        .join(' et ');
      description += ` à ${hours}`;
    } else if (hour !== '*') {
      const hourFormatted = hour.padStart(2, '0');
      const minuteFormatted = minute.padStart(2, '0');
      description += ` à ${hourFormatted}h${minuteFormatted}`;
    }

    return description;
  } catch {
    // Fallback: return raw expression
    return expression;
  }
}

/**
 * Preset cron expressions with French labels (Story 11.8, AC3).
 */
export interface CronPreset {
  label: string;
  value: string;
}

export const CRON_PRESETS: CronPreset[] = [
  { label: 'Chaque jour à 02:00', value: '0 2 * * *' },
  { label: 'Chaque lundi à 14:00', value: '0 14 * * 1' },
  { label: 'Chaque vendredi à 18:00', value: '0 18 * * 5' },
  { label: 'Tous les jours à 9h et 17h', value: '0 9,17 * * *' },
  { label: 'Le 1er de chaque mois à minuit', value: '0 0 1 * *' },
  { label: 'Toutes les 15 minutes', value: '*/15 * * * *' },
  { label: 'Tous les jours ouvrables à 2h', value: '0 2 * * 1-5' },
];

/**
 * Cron field documentation for helper modal (Story 11.8, AC9).
 */
export interface CronFieldDoc {
  name: string;
  description: string;
  values: string;
  examples: string[];
}

export const CRON_FIELD_DOCS: CronFieldDoc[] = [
  {
    name: 'Minute',
    description: 'Minute de l\'heure',
    values: '0-59, * (tous), */N (tous les N)',
    examples: ['0', '30', '*/15'],
  },
  {
    name: 'Heure',
    description: 'Heure du jour',
    values: '0-23, * (tous), */N (tous les N)',
    examples: ['2', '14', '9,17'],
  },
  {
    name: 'Jour',
    description: 'Jour du mois',
    values: '1-31, * (tous)',
    examples: ['1', '15', '*'],
  },
  {
    name: 'Mois',
    description: 'Mois de l\'année',
    values: '1-12, * (tous)',
    examples: ['1', '6', '*'],
  },
  {
    name: 'Jour de la semaine',
    description: '0=Dimanche, 1=Lundi, ..., 6=Samedi',
    values: '0-6, * (tous), 1-5 (jours ouvrables)',
    examples: ['1', '1-5', '0,6'],
  },
];

/**
 * Annotated examples for helper modal (Story 11.8, AC9).
 */
export interface CronExample {
  expression: string;
  description: string;
}

export const CRON_EXAMPLES: CronExample[] = [
  { expression: '0 2 * * *', description: 'Tous les jours à 2h00' },
  { expression: '0 14 * * 1', description: 'Tous les lundis à 14h00' },
  { expression: '0 0 1 * *', description: 'Le 1er de chaque mois à minuit' },
  { expression: '*/15 * * * *', description: 'Toutes les 15 minutes' },
  { expression: '0 9,17 * * 1-5', description: 'Jours ouvrables à 9h et 17h' },
];
