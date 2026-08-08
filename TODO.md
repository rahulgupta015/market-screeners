# TODO

## High priority
- [ ] Fix src/market_screeners/institution_accumulation.py, I think this file needs to go away as its already in src/market_screeners/screeners/institution.py, I want this to gel in with the current structure like src/market_screeners/screeners/multi_indicator.py  
- [ ] Fix src/market_screeners/option_analysis.py,  I think this file needs to go away as its already in src/market_screeners/screeners/institution.py, I want this to gel in with the current structure like src/market_screeners/screeners/multi_indicator.py
- [ ] Make sure tests run fine. I should be able to run all 3 indicators independently.
- [ ] The git cron workflow must invoke only src/market_screeners/screeners/multi_indicator.py
- [ ] Make sure that the html maintains the color when option analysis is run. It's not doing that as of now.
- [ ] Review the entire project and fix accordingly. 
- [ ] Fix read me file overall after all the above is done.
- [ ] All 3 screeners in src/market_screeners/screeners/ should be able to run independently per commands in readme and must generate html output.

## Improvements

## Bugs

## Ideas
