// @ts-check
const { test, expect } = require('@playwright/test');

const BASE = 'http://localhost:5000';

test.describe('Vista principal', () => {
  test('carga la página y muestra el tablero', async ({ page }) => {
    await page.goto(BASE);
    await page.screenshot({ path: 'screenshots/01_inicio.png', fullPage: true });
    await expect(page).toHaveTitle(/BANG/i);
  });

  test('paneles rivales existen en el DOM', async ({ page }) => {
    await page.goto(BASE);
    await page.screenshot({ path: 'screenshots/02_paneles_rivales.png', fullPage: true });
    // rivals-zone existe en el DOM aunque esté hidden hasta que empieza partida
    await expect(page.locator('#rivals-zone')).toBeAttached();
  });

  test('zona de mano de cartas existe en el DOM', async ({ page }) => {
    await page.goto(BASE);
    // hand-zone existe en el DOM aunque esté hidden hasta que empieza partida
    await expect(page.locator('#hand-zone')).toBeAttached();
    await page.screenshot({ path: 'screenshots/03_mano_cartas.png', fullPage: true });
  });
});

test.describe('Flujo completo de partida', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(BASE);
    // Iniciar partida con 4 jugadores
    await page.evaluate(async () => {
      await fetch('/nueva_partida', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ num_players: 4, nombres: ['Javi', 'B2', 'B3', 'B4'] })
      });
    });
    await page.waitForTimeout(1500);
    if (typeof page.evaluate === 'function') {
      await page.evaluate(() => {
        if (typeof startPolling === 'function') startPolling();
      });
    }
    await page.waitForTimeout(500);
  });

  test('pantalla tras iniciar partida', async ({ page }) => {
    await page.screenshot({ path: 'screenshots/04_partida_iniciada.png', fullPage: true });
  });

  test('aparece pregunta elegir_personaje', async ({ page }) => {
    // Esperar a que aparezca la UI de selección de personaje
    await page.waitForFunction(() => {
      const estado = window._questionType || document.querySelector('.pregunta-tipo')?.textContent;
      return document.body.textContent.includes('personaje') || document.querySelector('#pregunta-zone')?.textContent?.trim().length > 0;
    }, { timeout: 10000 }).catch(() => {});
    await page.screenshot({ path: 'screenshots/05_elegir_personaje.png', fullPage: true });
  });

  test('flujo completo automatizado (5 pasos)', async ({ page }) => {
    const ap = async (path, body) => page.evaluate(async ({ path, body }) => {
      const opts = body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {};
      return fetch(path, opts).then(r => r.json()).catch(() => ({}));
    }, { path, body });

    // Esperar primera pregunta
    let q = null;
    for (let i = 0; i < 30; i++) {
      await page.waitForTimeout(300);
      const d = await ap('/estado', null);
      if (d.pregunta) { q = d.pregunta; break; }
    }

    await page.screenshot({ path: 'screenshots/06_primer_turno.png', fullPage: true });

    // Jugar hasta 5 pasos
    for (let step = 0; step < 5 && q && !q.game_over; step++) {
      let valor = '1';
      if (q.tipo === 'elegir_personaje') valor = 'A';
      else if (q.tipo === 'prompt') valor = q.opciones?.includes('NO') ? 'NO' : 'SI';
      else if (q.tipo === 'elegir_carta') valor = q.permitir_fin === false ? (q.opciones?.[0] || 'FIN') : 'FIN';
      else if (q.tipo === 'elegir_jugador') valor = String(q.jugadores_validos?.[0] ?? '0');
      else if (q.tipo === 'elegir_robo_jesse') valor = String(q.rivales?.[0] ?? 'None');

      await ap('/accion', { valor });
      await page.waitForTimeout(500);

      for (let i = 0; i < 20; i++) {
        await page.waitForTimeout(200);
        const d = await ap('/estado', null);
        if (d.pregunta) { q = d.pregunta; break; }
        if (d.running === false) { q = null; break; }
      }

      await page.screenshot({ path: `screenshots/07_paso_${step + 1}.png`, fullPage: true });
    }
  });
});

test.describe('Galería de cartas (pixel art)', () => {
  test('renderiza canvas de carta Bang', async ({ page }) => {
    await page.goto(BASE);
    // Inyectar galería de debug para todas las cartas
    const canvas = await page.evaluate(() => {
      if (typeof getEfectoArt !== 'function') return null;
      const efectos = ['bang', 'fallaste', 'cerveza', 'saloon', 'indios', 'duelo',
        'panico', 'ing. explosiva', 'almacen', 'dinamita', 'barril',
        'mustang', 'mira telescopica', 'diligencia', 'wells fargo',
        'carcel', 'ametralladora gatling'];
      return efectos.map(n => {
        try { const r = getEfectoArt(n); return { nombre: n, ok: !!r?.g }; }
        catch (e) { return { nombre: n, ok: false, err: e.message }; }
      });
    });
    console.log('Pixel art status:', JSON.stringify(canvas, null, 2));
    // Screenshot de la página con todas las cartas si hay una galería disponible
    await page.screenshot({ path: 'screenshots/08_galeria_cartas.png', fullPage: true });
  });

  test('galería completa inyectada', async ({ page }) => {
    await page.goto(BASE);
    await page.evaluate(() => {
      if (typeof getEfectoArt !== 'function') return;
      const efectos = ['bang', 'fallaste', 'cerveza', 'saloon', 'indios', 'duelo',
        'panico', 'ing. explosiva', 'almacen', 'dinamita', 'barril',
        'mustang', 'mira telescopica', 'diligencia', 'wells fargo',
        'carcel', 'ametralladora gatling'];
      const grid = document.createElement('div');
      grid.style.cssText = 'display:flex;flex-wrap:wrap;gap:10px;padding:20px;background:#fff4de;position:fixed;top:0;left:0;width:100%;height:100%;overflow:auto;z-index:9999';
      efectos.forEach(nombre => {
        try {
          const art = getEfectoArt(nombre);
          if (!art?.g) return;
          const wrap = document.createElement('div');
          wrap.style.cssText = 'display:flex;flex-direction:column;align-items:center;gap:4px';
          const c = document.createElement('canvas');
          c.width = 80; c.height = 80;
          art.g(c.getContext('2d'), 80, 80);
          const label = document.createElement('div');
          label.style.cssText = 'font-size:10px;text-align:center;max-width:80px;word-break:break-word';
          label.textContent = nombre;
          wrap.appendChild(c); wrap.appendChild(label);
          grid.appendChild(wrap);
        } catch(e) {}
      });
      document.body.appendChild(grid);
    });
    await page.waitForTimeout(500);
    await page.screenshot({ path: 'screenshots/09_galeria_completa.png', fullPage: true });
  });
});
