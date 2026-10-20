// Turns the text result of a backend tool into data for an action card.
// Only successful actions become cards (refusals/errors are explained by the bot's reply).
export function toCard(event) {
  const r = event.result || "";

  if (event.name === "get_order_status") {
    const m = r.match(
      /^Order (\d+): (.+?), amount \$([\d.]+), status: (\w+), ETA: (.+?), ship to: (.+?), refund: (.+?), customer:/
    );
    if (m) {
      return { kind: "order", id: m[1], item: m[2], amount: m[3], status: m[4], eta: m[5], address: m[6], refund: m[7] };
    }
  }
  if (event.name === "process_refund") {
    const m = r.match(/^Refund of \$([\d.]+) for order (\d+) processed\. Reference: (\S+)/);
    if (m) return { kind: "refund", amount: m[1], orderId: m[2], reference: m[3] };
  }
  if (event.name === "update_record") {
    const m = r.match(/^Order (\d+): (\w+) updated to '(.*)'\./);
    if (m) return { kind: "update", orderId: m[1], field: m[2], value: m[3] };
  }
  if (event.name === "send_email") {
    const m = r.match(/^Email sent to (\S+) with subject '(.*)'\./);
    if (m) return { kind: "email", to: m[1], subject: m[2] };
  }
  if (event.name === "request_verification" && r.startsWith("If that order number is valid")) {
    return { kind: "code_sent" };
  }
  if (event.name === "confirm_verification" && r.startsWith("VERIFIED")) {
    return { kind: "verified" };
  }
  if (event.name === "check_ticket_status") {
    const m = r.match(/^Ticket #(\d+): (.+), status: (open|in_progress|resolved), message from support: ([\s\S]*)$/);
    if (m) return { kind: "ticket", id: m[1], reason: m[2], status: m[3], note: m[4] };
  }
  return null;
}
