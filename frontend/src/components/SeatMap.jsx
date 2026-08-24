export default function SeatMap({ data, selected, onToggle }) {
  if (!data) return <p>Loading seat map…</p>
  const grouped = Object.groupBy ? Object.groupBy(data.seats, (seat) => seat.row_label) : data.seats.reduce((acc, seat) => ((acc[seat.row_label] ||= []).push(seat), acc), {})
  return <div className="overflow-x-auto">
    <div className="mx-auto mb-8 w-2/3 border-t-4 border-gray-400 pt-2 text-center text-xs uppercase tracking-widest text-gray-500">Stage / Screen</div>
    <div className="min-w-max space-y-2">
      {Object.entries(grouped).map(([row, seats]) => <div key={row} className="flex items-center gap-2"><span className="w-6 text-center text-xs font-semibold text-gray-500">{row}</span>
        {seats.map((seat) => {
          const active = selected.includes(seat.id)
          const disabled = seat.status !== 'available'
          return <button key={seat.id} title={`${seat.category_name} · ₹${seat.price}`} disabled={disabled} onClick={() => onToggle(seat)}
            className={`h-9 w-9 rounded border text-xs font-semibold ${active ? 'border-amber-600 bg-amber-500 text-black' : disabled ? 'cursor-not-allowed border-gray-200 bg-gray-200 text-gray-500' : 'border-gray-400 bg-white hover:border-amber-500'}`}>
            {seat.seat_number}
          </button>
        })}
      </div>)}
    </div>
  </div>
}

