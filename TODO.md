# TODO

## High priority

- [ ] I don't like dsm. I think we can rename the entire project as stock screener and then update the entire structure accordingly. Not sure how git remote will react to it.
- [ ]

## Improvements

- [ ] Update the README. Also generate a `dma-and-car-logic.md` file, or another clear name, with a detailed logic explanation.
- [x] DMA BO logic - make independent of Zone -> CMP > 50 DMA > 100 DMA > 200 DMA, 200 DMA < CMP < 10% of 200 DMA - sort by shift% asc
- [x] CAR BO logic - make independent of Zone -> CMP > 50 DMA, CMP > 100 DMA, CMP > 200 DMA, 200 DMA < CMP < 10% of 200 DMA, CAR >= 5 - sort by CAR desc, shift% asc
- [ ] Zone logic - Fix logic. The zone logic does not play any role in DMA BO and CAR BO.

## Bugs

- [ ]

## Ideas

- [ ]
