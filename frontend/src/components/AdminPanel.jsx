import { Fragment, useCallback, useEffect, useState } from "react";
import {
  AuthError, adminLogin, adminLogout, createOrder, getCustomers, getOrders, getTickets, getToken, updateTicket,
} from "../api.js";

const STATUSES = ["open", "in_progress", "resolved"];
const LABEL = { open: "open", in_progress: "in progress", resolved: "resolved" };

const formatDate = (iso) => new Date(iso).toLocaleString();

function LoginForm({ onLoggedIn }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await adminLogin(password);
      onLoggedIn();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="login" onSubmit={submit}>
      <h2>Admin login</h2>
      <p>Enter the admin password to see tickets and orders.</p>
      <input
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        placeholder="Password"
        autoFocus
      />
      {error && <div className="alert">{error}</div>}
      <button type="submit" disabled={busy || !password}>
        {busy ? "Checking..." : "Log in"}
      </button>
    </form>
  );
}

function TicketDetail({ ticket, onSaved, onAuthLost }) {
  const [status, setStatus] = useState(ticket.status);
  const [note, setNote] = useState("");
  const [notify, setNotify] = useState(Boolean(ticket.contact_email));
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState(null);

  async function save() {
    setSaving(true);
    setFeedback(null);
    try {
      const updated = await updateTicket(ticket.id, { status, note, notify });
      onSaved(updated);
      setNote("");
      const n = updated.notification || "";
      setFeedback({ ok: !n.startsWith("failed"), text: `Saved. Email to customer: ${n}` });
    } catch (err) {
      if (err instanceof AuthError) onAuthLost();
      else setFeedback({ ok: false, text: err.message });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="ticket-detail">
      <strong>Summary from the AI assistant</strong>
      <p>{ticket.summary}</p>
      <div className="meta">
        Contact email: {ticket.contact_email ? <b>{ticket.contact_email}</b> : <b>none (customer cannot be emailed)</b>}
      </div>
      {ticket.resolution_note && (
        <div className="meta">
          Last message to the customer: <i>{ticket.resolution_note}</i>
        </div>
      )}

      <div className="update-form">
        <label>
          Status
          <select className={`status ${status}`} value={status} onChange={(e) => setStatus(e.target.value)}>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {LABEL[s]}
              </option>
            ))}
          </select>
        </label>
        <label className="grow">
          Message for the customer (optional)
          <textarea
            rows={3}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="e.g. Your refund has been processed and will reach your card in 5-7 days."
            maxLength={2000}
          />
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={notify}
            disabled={!ticket.contact_email}
            onChange={(e) => setNotify(e.target.checked)}
          />
          Email the customer about this update
        </label>
        <button onClick={save} disabled={saving}>
          {saving ? "Saving..." : "Save update"}
        </button>
        {feedback && <div className={feedback.ok ? "notice ok" : "alert"}>{feedback.text}</div>}
      </div>
    </div>
  );
}

function TicketsTable({ tickets, onSaved, onAuthLost }) {
  const [openId, setOpenId] = useState(null);
  if (tickets.length === 0) return <p className="empty">No tickets yet.</p>;
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Reason</th>
            <th>Customer</th>
            <th>Order</th>
            <th>Created</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {tickets.map((t) => (
            <Fragment key={t.id}>
              <tr className="clickable" onClick={() => setOpenId(openId === t.id ? null : t.id)}>
                <td>{t.id}</td>
                <td>{t.reason}</td>
                <td>
                  {t.customer_name || "-"}
                  {t.contact_email && (
                    <>
                      <br />
                      <small>{t.contact_email}</small>
                    </>
                  )}
                </td>
                <td>{t.order_id ? `#${t.order_id}` : "-"}</td>
                <td>{formatDate(t.created_at)}</td>
                <td>
                  <span className={`pill ${t.status}`}>{LABEL[t.status]}</span>
                </td>
              </tr>
              {openId === t.id && (
                <tr className="detail">
                  <td colSpan={6}>
                    <TicketDetail ticket={t} onSaved={onSaved} onAuthLost={onAuthLost} />
                  </td>
                </tr>
              )}
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function OrdersTable({ orders }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Order</th>
            <th>Item</th>
            <th>Amount</th>
            <th>Status</th>
            <th>Customer</th>
            <th>Payment</th>
            <th>Refund</th>
          </tr>
        </thead>
        <tbody>
          {orders.map((o) => (
            <tr key={o.id}>
              <td>#{o.id}</td>
              <td>{o.item}</td>
              <td>${o.amount.toFixed(2)}</td>
              <td>{o.status}</td>
              <td>
                {o.customer_name}
                <br />
                <small>{o.customer_email}</small>
              </td>
              <td>{o.payment_intent_id ? <small>{o.payment_intent_id}</small> : "-"}</td>
              <td>{o.refunded ? `Refunded (${o.refund_reference})` : "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const ORDER_STATUSES = ["processing", "shipped", "delivered", "cancelled"];

function AddOrderForm({ onCreated, onAuthLost }) {
  const [customers, setCustomers] = useState([]);
  const [customerId, setCustomerId] = useState(""); // "" | customer id | "new"
  const [nc, setNc] = useState({ name: "", email: "", phone: "" });
  const [f, setF] = useState({ item: "", amount: "", status: "processing", eta: "", shipping_address: "", create_payment: true });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getCustomers()
      .then(setCustomers)
      .catch((err) => (err instanceof AuthError ? onAuthLost() : setError("Could not load customers.")));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const isNew = customerId === "new";
  const valid =
    customerId !== "" &&
    (!isNew || (nc.name.trim() && nc.email.trim())) &&
    f.item.trim() &&
    Number(f.amount) > 0;

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    const payload = {
      ...(isNew
        ? { new_customer: { name: nc.name, email: nc.email, phone: nc.phone || null } }
        : { customer_id: Number(customerId) }),
      item: f.item,
      amount: Number(f.amount),
      status: f.status,
      eta: f.eta || null,
      shipping_address: f.shipping_address || null,
      create_payment: f.create_payment,
    };
    try {
      const order = await createOrder(payload);
      onCreated(order);
    } catch (err) {
      if (err instanceof AuthError) onAuthLost();
      else setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="add-order" onSubmit={submit}>
      <h3>Add an order</h3>
      <label className="wide">
        Customer
        <select value={customerId} onChange={(e) => setCustomerId(e.target.value)}>
          <option value="">Choose a customer...</option>
          {customers.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name} ({c.email})
            </option>
          ))}
          <option value="new">+ New customer</option>
        </select>
      </label>

      {isNew && (
        <>
          <label>
            Customer name
            <input value={nc.name} onChange={(e) => setNc({ ...nc, name: e.target.value })} maxLength={100} />
          </label>
          <label>
            Customer email (must be unique)
            <input type="email" value={nc.email} onChange={(e) => setNc({ ...nc, email: e.target.value })} maxLength={150} />
          </label>
          <label>
            Phone (optional)
            <input value={nc.phone} onChange={(e) => setNc({ ...nc, phone: e.target.value })} maxLength={30} />
          </label>
        </>
      )}

      <label>
        Item
        <input value={f.item} onChange={(e) => setF({ ...f, item: e.target.value })} maxLength={150} />
      </label>
      <label>
        Amount (USD)
        <input type="number" min="0.01" step="0.01" value={f.amount} onChange={(e) => setF({ ...f, amount: e.target.value })} />
      </label>
      <label>
        Status
        <select value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })}>
          {ORDER_STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </label>
      <label>
        ETA (optional)
        <input value={f.eta} placeholder="e.g. 3 days" onChange={(e) => setF({ ...f, eta: e.target.value })} maxLength={50} />
      </label>
      <label className="wide">
        Shipping address (optional)
        <input value={f.shipping_address} onChange={(e) => setF({ ...f, shipping_address: e.target.value })} maxLength={255} />
      </label>

      <label className="check wide">
        <input
          type="checkbox"
          checked={f.create_payment}
          onChange={(e) => setF({ ...f, create_payment: e.target.checked })}
        />
        <span>
          Customer already paid by card (a Stripe test payment is created now, and a later refund will use it)
          <small className="hint">Cash on delivery? Untick this box.</small>
        </span>
      </label>

      {error && <div className="alert wide">{error}</div>}
      <div className="wide">
        <button type="submit" className="primary" disabled={busy || !valid}>
          {busy ? "Saving..." : "Save order"}
        </button>
      </div>
    </form>
  );
}

export default function AdminPanel() {
  const [loggedIn, setLoggedIn] = useState(Boolean(getToken()));
  const [view, setView] = useState("tickets");
  const [tickets, setTickets] = useState([]);
  const [orders, setOrders] = useState([]);
  const [error, setError] = useState("");
  const [showAdd, setShowAdd] = useState(false);
  const [notice, setNotice] = useState(null); // { text, warn }

  const load = useCallback(async () => {
    try {
      const [t, o] = await Promise.all([getTickets(), getOrders()]);
      setTickets(t);
      setOrders(o);
      setError("");
    } catch (err) {
      if (err instanceof AuthError) setLoggedIn(false);
      else setError("Could not load data. Is the backend running?");
    }
  }, []);

  useEffect(() => {
    if (!loggedIn) return;
    load();
    const id = setInterval(load, 10000); // auto refresh
    return () => clearInterval(id);
  }, [loggedIn, load]);

  async function logout() {
    await adminLogout();
    setTickets([]);
    setOrders([]);
    setLoggedIn(false);
  }

  if (!loggedIn) return <LoginForm onLoggedIn={() => setLoggedIn(true)} />;

  const open = tickets.filter((t) => t.status !== "resolved").length;
  const replaceTicket = (updated) => setTickets((list) => list.map((t) => (t.id === updated.id ? updated : t)));

  return (
    <div className="admin">
      <div className="admin-top">
        <div className="subtabs">
          <button className={view === "tickets" ? "sub active" : "sub"} onClick={() => setView("tickets")}>
            Tickets {open > 0 && <span className="count">{open}</span>}
          </button>
          <button className={view === "orders" ? "sub active" : "sub"} onClick={() => setView("orders")}>
            Orders
          </button>
        </div>
        <div className="actions">
          <button className="ghost" onClick={load}>
            ↻ Refresh
          </button>
          <button className="ghost" onClick={logout}>
            Log out
          </button>
        </div>
      </div>
      {error && <div className="alert">{error}</div>}
      {view === "tickets" ? (
        <TicketsTable tickets={tickets} onSaved={replaceTicket} onAuthLost={() => setLoggedIn(false)} />
      ) : (
        <>
          <div className="orders-bar">
            <button className="primary" onClick={() => setShowAdd((v) => !v)}>
              {showAdd ? "Close form" : "+ Add order"}
            </button>
          </div>
          {notice && <div className={notice.warn ? "notice warn" : "notice ok"}>{notice.text}</div>}
          {showAdd && (
            <AddOrderForm
              onAuthLost={() => setLoggedIn(false)}
              onCreated={async (order) => {
                setShowAdd(false);
                const base = `Order #${order.id} added for ${order.customer_name} (${order.customer_email}).`;
                setNotice(
                  order.payment_warning
                    ? { warn: true, text: `${base} ${order.payment_warning}` }
                    : { warn: false, text: order.payment_intent_id ? `${base} Stripe test payment: ${order.payment_intent_id}.` : base }
                );
                await load();
              }}
            />
          )}
          <OrdersTable orders={orders} />
        </>
      )}
    </div>
  );
}
