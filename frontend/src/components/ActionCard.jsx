const STATUS_CLASS = {
  processing: "badge warn",
  shipped: "badge info",
  delivered: "badge ok",
  cancelled: "badge bad",
  refunded: "badge info",
};

function Row({ label, value }) {
  return (
    <div className="card-row">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export function ActionCard({ card }) {
  if (card.kind === "order") {
    return (
      <div className="card">
        <div className="card-title">📦 Order #{card.id}</div>
        <Row label="Item" value={card.item} />
        <Row label="Amount" value={`$${card.amount}`} />
        <div className="card-row">
          <span>Status</span>
          <span className={STATUS_CLASS[card.status] || "badge"}>{card.status}</span>
        </div>
        <Row label="ETA" value={card.eta} />
        <Row label="Ship to" value={card.address} />
        <Row label="Refund" value={card.refund} />
      </div>
    );
  }
  if (card.kind === "refund") {
    return (
      <div className="card card-ok">
        <div className="card-title">✅ Refund processed</div>
        <Row label="Order" value={`#${card.orderId}`} />
        <Row label="Amount" value={`$${card.amount}`} />
        <Row label="Reference" value={card.reference} />
      </div>
    );
  }
  if (card.kind === "update") {
    return (
      <div className="card card-ok">
        <div className="card-title">✏️ Record updated</div>
        <Row label="Order" value={`#${card.orderId}`} />
        <Row label="Field" value={card.field} />
        <Row label="New value" value={card.value} />
      </div>
    );
  }
  if (card.kind === "email") {
    return (
      <div className="card">
        <div className="card-title">✉️ Confirmation email sent</div>
        <Row label="To" value={card.to} />
        <Row label="Subject" value={card.subject} />
      </div>
    );
  }
  if (card.kind === "code_sent") {
    return (
      <div className="card">
        <div className="card-title">📧 Verification code</div>
        <div className="card-row">
          <span>If the order number is valid, a 6-digit code was emailed to the address on the order. Type it in the chat (valid for 10 minutes).</span>
        </div>
      </div>
    );
  }
  if (card.kind === "verified") {
    return (
      <div className="card card-ok">
        <div className="card-title">✅ Identity verified</div>
        <div className="card-row">
          <span>You can now manage your own orders in this chat for 30 minutes.</span>
        </div>
      </div>
    );
  }
  if (card.kind === "ticket") {
    const cls = { open: "badge warn", in_progress: "badge info", resolved: "badge ok" }[card.status] || "badge";
    return (
      <div className="card">
        <div className="card-title">🎫 Ticket #{card.id}</div>
        <Row label="Reason" value={card.reason} />
        <div className="card-row">
          <span>Status</span>
          <span className={cls}>{card.status.replace("_", " ")}</span>
        </div>
        <Row label="Message from support" value={card.note} />
      </div>
    );
  }
  return null;
}

export function EscalationBanner({ ticketId }) {
  return (
    <div className="banner">
      <span>🧑‍💼</span>
      <div>
        <strong>Forwarded to a human agent</strong>
        <div>Ticket #{ticketId}. You will get a reply within 24 hours.</div>
      </div>
    </div>
  );
}
