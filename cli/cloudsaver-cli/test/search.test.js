import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { Command } from 'commander';
import { searchCommand } from '../src/commands/search.js';
import { ConfigManager } from '../src/config/index.js';
import { Searcher } from '../src/services/Searcher.js';

function result(id, overrides = {}) {
  return {
    messageId: id,
    title: '1080P WEB-DL',
    content: '',
    tags: [],
    channel: 'fixture',
    pubDate: '2026-01-01T00:00:00Z',
    cloudLinks: [{ type: 'pan115', url: `https://115.com/s/${id}` }],
    ...overrides,
  };
}

test('bounded workers preserve channel order when tied results finish out of order', async () => {
  const searcher = new Searcher({});
  const channels = Array.from({ length: 6 }, (_, i) => ({ id: String(i) }));
  const pending = new Map();
  const requested = [];
  searcher.searchChannel = async (channel, keyword) => {
    assert.equal(keyword, 'fixture');
    requested.push(channel.id);
    await new Promise((resolve) => pending.set(channel.id, resolve));
    return [result(channel.id)];
  };

  const response = searcher.searchAll('fixture', channels, 2);
  assert.deepEqual(requested, ['0', '1']);
  for (const id of ['1', '2', '3', '0', '5', '4']) {
    assert.ok(pending.has(id));
    pending.get(id)();
    pending.delete(id);
    await new Promise((resolve) => setImmediate(resolve));
    assert.ok(pending.size <= 2);
  }
  assert.deepEqual(requested, channels.map(({ id }) => id));
  assert.deepEqual((await response).map(({ messageId }) => messageId), requested);
});

test('ranking keeps cloud, clarity, time priorities and stable ties', async () => {
  const searcher = new Searcher({});
  const rows = [
    result('ali', { title: '8K REMUX', cloudLinks: [{ type: 'aliyun' }] }),
    result('720', { title: '720P' }),
    result('old', { title: '4K HDR', pubDate: '2025-01-01' }),
    result('new', { title: '4K HDR', pubDate: '2026-01-01' }),
    result('tie', { title: '4K HDR', pubDate: '2026-01-01' }),
    result('1080'),
  ];
  searcher.searchChannel = async () => rows;
  const ranked = await searcher.searchAll('', [{ id: 'channel' }]);
  assert.deepEqual(ranked.map(({ messageId }) => messageId), ['new', 'tie', 'old', '1080', '720', 'ali']);
  assert.deepEqual(rows.map(({ messageId }) => messageId), ['ali', '720', 'old', 'new', 'tie', '1080']);
  assert.equal(ranked[0], rows[3]);
});

test('serial mode waits for each request and missing dates stay stable', async () => {
  const searcher = new Searcher({});
  let active = false;
  searcher.searchChannel = async ({ id }) => {
    assert.equal(active, false);
    active = true;
    await new Promise((resolve) => setImmediate(resolve));
    active = false;
    return [result(id, { pubDate: '' })];
  };
  const ranked = await searcher.searchAll('', [{ id: 'a' }, { id: 'b' }], 1);
  assert.deepEqual(ranked.map(({ messageId }) => messageId), ['a', 'b']);
});

test('one failed channel does not discard successful channels', async (t) => {
  t.mock.method(console, 'error', () => {});
  const searcher = new Searcher({
    async get(url) {
      if (url.startsWith('/failed')) throw new Error('fixture failure');
      return { data: `<div class="tgme_widget_message_wrap">
        <div class="tgme_widget_message" data-post="ok/42">
          <div class="js-message_text tgme_widget_message_text">Movie 4K<br><a href="https://115.com/s/fixture">Link</a></div>
          <time datetime="2026-01-01"></time>
        </div></div>` };
    },
  });
  const ranked = await searcher.searchAll('中文', [{ id: 'failed', name: 'failed' }, { id: 'ok', name: 'ok' }]);
  assert.equal(ranked.length, 1);
  assert.equal(ranked[0].messageId, '42');
  assert.equal(ranked[0].cloudLinks[0].url, 'https://115.com/s/fixture');
  assert.equal(console.error.mock.callCount(), 1);
});

test('invalid concurrency fails before requesting any channel', async () => {
  const searcher = new Searcher({});
  searcher.searchChannel = async () => assert.fail('must not request');
  for (const concurrency of [0, -1, 1.5, 17, NaN, '4']) {
    await assert.rejects(searcher.searchAll('', [{ id: 'fixture' }], concurrency), /1-16/);
  }
  assert.deepEqual(await searcher.searchAll('', []), []);
});

test('search command loads both output formats lazily and forwards concurrency', async (t) => {
  t.mock.method(ConfigManager, 'load', () => ({ search: { channels: [{ id: 'fixture' }] } }));
  t.mock.method(Searcher.prototype, 'searchAll', async (keyword, channels, concurrency) => {
    assert.equal(keyword, 'movie');
    assert.deepEqual(channels, [{ id: 'fixture' }]);
    assert.equal(concurrency, 3);
    return [result('movie')];
  });
  const output = [];
  t.mock.method(console, 'log', (...args) => output.push(args.join(' ')));
  for (const format of [[], ['--no-table']]) {
    const program = new Command();
    searchCommand(program);
    await program.parseAsync(['node', 'fixture', 'search', 'movie', '--concurrency', '3', ...format]);
    assert.ok(output.some((line) => line.includes('https://115.com/s/movie')));
    output.length = 0;
  }
});

test('shipped wrapper forwards CLI flags and rejects invalid concurrency without configuration', () => {
  const executable = fileURLToPath(new URL('../cloudsaver-cli', import.meta.url));
  const help = spawnSync('bash', [executable, 'search', '--help'], { encoding: 'utf8' });
  assert.equal(help.status, 0, help.stderr);
  assert.match(help.stdout, /--concurrency/);
  const invalid = spawnSync('bash', [executable, 'search', 'fixture', '--concurrency', '0'], { encoding: 'utf8' });
  assert.equal(invalid.status, 1);
  assert.match(invalid.stderr, /1-16/);
});
