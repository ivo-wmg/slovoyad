from scraper import scrape_article
r = scrape_article('https://money.bg/companies/grazhdanite-shte-si-poluchat-dalzhimite-obeshtenia-ot-zastrahovatelia-dallbogg-zhivot-i-zdrave-do-poslednata-stotinka.html')
print('Authors:', r.get('authors'))
print('Date:', r.get('publish_date'))
