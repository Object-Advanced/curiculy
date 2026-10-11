# Style tiles and the kid pages

## The canvas
All design boards live on one canvas: **[Curiculy Style Tiles](https://claude.ai/artifact/3VsX9TqdT7HK7nLyL1MdD2)**. It's private to the owner; use its Share menu to show someone. It has three rows.

| Row | Boards | Status |
|---|---|---|
| **Chosen** (bottom) | Parent "Morning Light" with Newsreader headlines · Kid **My trail** · Kid **Sticker journal** | The direction we're building |
| **Parent options** | A · Morning Light · B · Field Notes · C · Soft Social | A was chosen, borrowing B's serif headlines |
| **Kid options** | A · Sticker Book · B · Explorer Trail | A was chosen; Explorer Trail became the **My trail** page |

## My trail (kid)
A playful page a child opens to see their day as a path. **It will be built as the first React screen** (Phase 3).

- **Stops are today's lessons, in order.** Each says where it comes from ("Grab your copy", "Blue workbook, p. 14"), with an **I did it!** button at the current stop.
- **The bonus chest** is the daily "Just for fun" puzzle, on a side path, so it's optional.
- **Camp** is reached when every stop is done. It earns that month's **seasonal sticker** (October: Acorn, Maple leaf, Apple, Owl, Pumpkin…), and **cheers from parents** wait there.
- **Today's stickers** panel: one slot per stop, the bonus, and the camp prize.
- **No guilt:** a missed camp is an empty dashed tent, never a red mark.

## Sticker journal (kid)
- **This week page:** each day's stickers, a tent on days the child reached camp, and today's "stops to go".
- **The month's collection:** 8 seasonal stickers. Earned ones show; the next is "Today's prize"; the rest are mysteries.
- **Cheers from home:** stickers parents sent ("Great job!", "So proud!").
- **Tap a sticker** to see which lesson earned it.

## How stickers will work (proposed)
- **Stickers are worked out from completed lessons**, so there's no separate sticker table, and the journal fills in automatically from work done since the beta started.
- **Unchecking a lesson removes its sticker.**
- **Needs first:** checking a lesson off must record its `completion_date` (today it only changes the status). See [Calendar](../2-features/04-calendar-and-lessons.md).
- **Cheers need one small new table** (`assignment_reactions`) and a "Cheer" button on the parent's feed.

## Principles for every kid screen
1. **Guide, don't teach.** Point to the family's own materials.
2. **Fun is optional.** Puzzles and stickers are play and rewards, never instruction.
3. **Encouraging, never shaming.**
4. **Big targets** (at least 44 px), made for tablets first.
5. **Every screen passes the accessibility scan**, including the kid look.
