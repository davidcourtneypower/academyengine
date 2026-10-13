# FC27 Academy Engine v1.24.35 — Face picker loading fixes

- **50 faces per batch** for every region (Load more adds 50), whatever the window size.
- **No more 1000-face loads**: opening the picker used to load every face up to the player's current
  one, which could be hundreds in a large region. It now loads one batch and shows the current face
  first (outlined "Current") until Load more reaches its place in the list.
- **Blank faces fixed**: the thumbnail cache kept only the newest 400 images and deleted older ones while
  a long list still used them, so most tiles in a big list were blank. It now keeps up to 4,000
  (about 110 MB), cleans up at most every 10 minutes, and never removes a thumbnail used in the last
  30 minutes.
- Load more stops at 950 faces per region (the overlay's limit) and says so, instead of waiting forever.
