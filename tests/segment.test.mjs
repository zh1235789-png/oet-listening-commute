// 文の区切り（build/segment.py）。Python を呼んで結果を見る。
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';

const BUILD = new URL('../build', import.meta.url).pathname;
function seg(words, dur) {
  const code = `import sys,json; sys.path.insert(0, ${JSON.stringify(BUILD)}); from segment import segment; print(json.dumps(segment(json.loads(sys.stdin.read()), ${dur ?? 'None'})))`;
  const r = spawnSync('python3', ['-c', code], { input: JSON.stringify(words), encoding: 'utf8' });
  if (r.status !== 0) throw new Error(r.stderr);
  return JSON.parse(r.stdout);
}
const W = (s, e, t) => [s, e, ' ' + t];

test('ピリオドで区切り、Mr. などの略語では区切らない', () => {
  const out = seg([W(1, 1.3, 'Come'), W(1.3, 1.5, 'in.'), W(1.6, 1.8, "It's"), W(1.8, 2.1, 'Mr.'), W(2.1, 2.5, 'Sands,'), W(2.5, 2.8, "isn't"), W(2.8, 3.0, 'it?'),
    W(3.2, 3.5, 'That'), W(3.5, 3.8, 'is'), W(3.8, 4.2, 'right.')]);
  // "Come in." は2語なので次とつながる
  assert.deepEqual(out.map((s) => s[2]), ["Come in. It's Mr. Sands, isn't it?", 'That is right.']);
});

test('長い無音（1.2秒以上）でも区切る', () => {
  const out = seg([W(1, 1.5, 'Extract'), W(1.5, 2, 'one'), W(5, 5.5, 'You'), W(5.5, 6, 'hear'), W(6, 6.5, 'a'), W(6.5, 7, 'nurse.')]);
  assert.equal(out.length, 2);
  assert.equal(out[0][2], 'Extract one');
});

test('前後に少し余白を付けるが、隣の文の語には食い込まない', () => {
  const out = seg([W(1, 1.5, 'One'), W(1.5, 2, 'two'), W(2, 2.5, 'three.'), W(2.6, 3, 'Four'), W(3, 3.5, 'five'), W(3.5, 4, 'six.')], 10);
  assert.equal(out[0][0], 0.85);
  assert.ok(out[0][1] <= 2.6, '前の文の終わりが次の文の最初の語を越えない ' + JSON.stringify(out));
  assert.ok(out[1][0] >= 2.5, '次の文の始まりが前の文の最後の語に食い込まない ' + JSON.stringify(out));
  assert.ok(out[1][1] <= 10);
  for (let i = 1; i < out.length; i++) assert.ok(out[i][0] >= out[i - 1][0]);
});

function instr(texts) {
  const code = `import sys,json; sys.path.insert(0, ${JSON.stringify(BUILD)}); from segment import is_instruction; print(json.dumps([is_instruction(t) for t in json.loads(sys.stdin.read())]))`;
  const r = spawnSync('python3', ['-c', code], { input: JSON.stringify(texts), encoding: 'utf8' });
  if (r.status !== 0) throw new Error(r.stderr);
  return JSON.parse(r.stdout);
}

test('試験の指示文は除き、本文は残す', () => {
  const drop = ['Now read the question.', 'Now, read the question.', 'Question 3. Now read the question.', 'Extract 1, questions 1 to 12.',
    'Extract two. Questions thirteen to twenty-four.', 'You now have 90 seconds to read questions 1 to 6.', 'You now have 30 seconds to look at the notes.',
    'For questions 1 to 12, complete the notes with a word or short phrase.', 'For questions 25-30, choose the answer A, B or C, which fits best according to what you hear.',
    'Complete your answers as you listen.', 'That is the end of part A. Now look at part B.', 'That is the end of the listening test.',
    'Part C. In this part of the test, you\'ll hear two different extracts.', 'In each extract, a health professional is talking to a patient.',
    'At the start of each extract, you\'ll hear this sound.', 'Now turn over and look at the notes for Extract 2.'];
  const keep = ['That\'s a good question.', 'Do you have any other questions for me?', 'Sure, I can look at that for you.', 'And look at my ankles.',
    'People typically use either 2 or 3 seconds, which is still fairly quick.', 'You hear a nurse briefing a colleague at the end of her shift.',
    'Question 3. You hear a doctor advising a patient about a change in medication.', 'kidney problems. Now, read the question.', 'And that\'s actually the end of the procedure.'];
  assert.deepEqual(instr(drop), drop.map(() => true), '指示文');
  assert.deepEqual(instr(keep), keep.map(() => false), '本文');
});
