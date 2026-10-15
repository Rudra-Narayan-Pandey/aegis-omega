'use client';

import React, { useState, useEffect } from 'react';

export default function ThreatRadar() {
  const [events, setEvents] = useState([
    { id: 'evt-001', ip: '198.51.100.42', threat: 'MCP Schema Poisoning', status: 'AUTO_PATCHED', cost: 14.82, time: '17:28:10 UTC' }
  ]);
  const [budget, setBudget] = useState(14.82);

  // Simulates the live WebSocket feed from our Python Gateway
  useEffect(() => {
    const interval = setInterval(() => {
      const newEvent = {
        id: `evt-${Date.now().toString().slice(-4)}`,
        ip: `192.0.2.${Math.floor(Math.random() * 255)}`,
        threat: Math.random() > 0.5 ? 'Prompt Injection' : 'TOCTOU CDA Exploit',
        status: 'TRAPPED IN HONEYPOT',
        cost: parseFloat((Math.random() * 5).toFixed(2)),
        time: new Date().toISOString().substring(11, 19) + ' UTC'
      };
      setEvents(prev => [newEvent, ...prev.slice(0, 4)]);
      setBudget(prev => parseFloat((prev + newEvent.cost).toFixed(2)));
    }, 4500);
    return () => clearInterval(interval);
  }, []);

  return (
    <main style={{ backgroundColor: '#020617', color: '#f8fafc', minHeight: '100vh', padding: '2rem', fontFamily: 'monospace' }}>
      <header style={{ borderBottom: '1px solid #06b6d4', paddingBottom: '1rem', marginBottom: '2rem', display: 'flex', justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ color: '#22d3ee', fontSize: '1.5rem', fontWeight: 'bold' }}>AEGISAGENT OMEGA // SOC RADAR</h1>
          <p style={{ color: '#94a3b8', fontSize: '0.75rem' }}>AUTONOMOUS COUNTER-AI DEFENSE MESH</p>
        </div>
        <div style={{ color: '#10b981', fontWeight: 'bold' }}>● MESH ONLINE</div>
      </header>

      <div style={{ display: 'flex', gap: '1rem', marginBottom: '2rem' }}>
        <div style={{ border: '1px solid #1e293b', padding: '1rem', borderRadius: '4px', flex: 1 }}>
          <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>TARPIT BUDGET DRAINED</div>
          <div style={{ fontSize: '2rem', color: '#fbbf24', fontWeight: 'bold' }}>${budget.toFixed(2)}</div>
        </div>
        <div style={{ border: '1px solid #1e293b', padding: '1rem', borderRadius: '4px', flex: 1 }}>
          <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>SEMANTIC CACHE TTFT</div>
          <div style={{ fontSize: '2rem', color: '#22d3ee', fontWeight: 'bold' }}>&lt; 14 ms</div>
        </div>
      </div>

      <section style={{ border: '1px solid #1e293b', padding: '1.5rem', borderRadius: '4px' }}>
        <h2 style={{ fontSize: '0.875rem', color: '#cbd5e1', marginBottom: '1rem' }}>LIVE INTERCEPTED SWARM TELEMETRY</h2>
        <table style={{ width: '100%', textAlign: 'left', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid #1e293b', color: '#94a3b8' }}>
              <th style={{ padding: '0.5rem' }}>EVENT ID</th>
              <th>SOURCE IP</th>
              <th>ATTACK VECTOR</th>
              <th>COST DRAINED</th>
              <th>STATUS</th>
            </tr>
          </thead>
          <tbody>
            {events.map(evt => (
              <tr key={evt.id} style={{ borderBottom: '1px solid #0f172a' }}>
                <td style={{ padding: '0.5rem', color: '#67e8f9' }}>{evt.id}</td>
                <td>{evt.ip}</td>
                <td>{evt.threat}</td>
                <td style={{ color: '#fbbf24', fontWeight: 'bold' }}>${evt.cost.toFixed(2)}</td>
                <td style={{ color: '#fb923c' }}>{evt.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </main>
  );
}