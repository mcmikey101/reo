import { cx } from '../lib/cx'

// Кнопки по макету: размеры s и m, виды primary, secondary, ghost.
// Подходит и для <button>, и для <Link>: className={buttonClass({ kind: 'primary' })}

const sizes = {
  s: 'h-7.5 gap-1.5 px-2.5 text-small font-medium',
  m: 'h-9 gap-1.75 px-3.5 text-body font-medium',
} as const

const kinds = {
  primary: 'bg-accent text-white hover:bg-accent-hover',
  secondary: 'border border-input-line bg-surface text-ink hover:bg-hover',
  ghost: 'text-ink-2 hover:bg-hover hover:text-ink',
} as const

interface ButtonClassOptions {
  kind?: keyof typeof kinds
  size?: keyof typeof sizes
}

export function buttonClass({ kind = 'secondary', size = 'm' }: ButtonClassOptions = {}): string {
  return cx(
    'inline-flex shrink-0 cursor-pointer items-center justify-center rounded-ctl whitespace-nowrap transition-colors disabled:cursor-default disabled:opacity-45',
    sizes[size],
    kinds[kind],
  )
}
