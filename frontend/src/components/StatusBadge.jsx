export default function StatusBadge({ value }) {
  const tone = value === 'available' || value === 'confirmed' || value === 'published' || value === 'fulfilled'
    ? 'bg-green-50 text-green-700 border-green-200'
    : value === 'held' || value === 'pending' || value === 'waiting' || value === 'offered'
      ? 'bg-amber-50 text-amber-800 border-amber-200'
      : 'bg-gray-100 text-gray-700 border-gray-200'
  return <span className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-medium capitalize ${tone}`}>{value}</span>
}

