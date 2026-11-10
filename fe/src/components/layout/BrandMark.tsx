/** Знак сервиса из макета: облачко отзыва */
export function BrandMark({ className }: { className?: string }) {
  return (
    <svg aria-hidden className={className} viewBox="0 0 26 26" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path
        d="M6 3.5h14A3.5 3.5 0 0 1 23.5 7v8.5A3.5 3.5 0 0 1 20 19h-8.2l-4.6 3.6c-.5.4-1.2 0-1.2-.6v-3H6A3.5 3.5 0 0 1 2.5 15.5V7A3.5 3.5 0 0 1 6 3.5z"
        fill="currentColor"
      />
      <path d="M7.5 9.2h11M7.5 13.3h6.5" stroke="#FFFFFF" strokeWidth="2.1" strokeLinecap="round" />
    </svg>
  )
}
