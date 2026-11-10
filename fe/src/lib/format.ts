// Время в интерфейсе показываем по Москве (docs/api-contract.md, раздел 1.4)
const timeFormat = new Intl.DateTimeFormat('ru-RU', {
  timeZone: 'Europe/Moscow',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
})

/** «21:05:12» по Москве */
export function formatTime(date: Date | number): string {
  return timeFormat.format(date)
}
