// Which catalog block backs each layout name.
//
// A layout name is a closed set defined here; a caller can name a layout, never a
// file, so the trust boundary is unchanged (the design's D4). Only
// variable-declaring blocks are adopted (the design's D3): a component would need
// its content rewritten, which is the markup this migration removes.
//
// `origin` records whether this name still has a hand-written builder in
// src/layouts/. During the migration both work; when no origin remains, the
// layout builders are deleted.

export const BLOCK_LAYOUTS = {};

// A block name may also be addressed directly, so a spec can ask for a block that
// has no layout name of its own. This is the additive half of the migration: the
// block renders alongside the layouts, and a layout name switches over later.
export const BLOCK_NAMES = new Set(["bar-chart-race"]);

export const isBlock = (name) => Boolean(BLOCK_LAYOUTS[name]) || BLOCK_NAMES.has(name);
export const blockFor = (name) => (BLOCK_LAYOUTS[name] ? BLOCK_LAYOUTS[name].block : name);
