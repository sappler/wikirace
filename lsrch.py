import requests
from threading import Thread, Lock
import sys
from selectolax.parser import HTMLParser
from collections import defaultdict


#returns a HTTP parseable text stream 
def gettext(url):
    with requests.Session() as session:
        content = session.get(url).text
    return content

#checks if either article is "nonexistent" or is a dead-end
def verify_search(start, end):
    nodetext1 = gettext('https://en.wikipedia.org/wiki/' + start)
    if 'Wikipedia does not have an article with this exact name' in nodetext1:
        print('sorry, one or both of those pages does not exist')
        return False
    html = gettext(
        "https://en.wikipedia.org/w/index.php?title=Special:WhatLinksHere/" + end + "&namespace=0&limit=5&hideredirs=1&hidetrans=1")
    if 'No pages link to' in html:
        return False
    return True

#Performs BFS from the start article
def search(lock, table, start, path1):
    minlen = 100000
    queue = [start]
    seen = defaultdict(bool)
    seen[start] = True #puts first article in dict
    while queue:
        node = queue.pop(0)
        html = gettext('https://en.wikipedia.org/wiki/' + node) #gets page text
        if html is None:
            continue
        parsed = HTMLParser(html)
        div = parsed.css_first('div.mw-parser-output') #main article text
        if div is None:
            continue
        for tag in div.css('a'): #for all links in the article:
            att = tag.attrs
            try:
                href = att['href']
            except:
                continue
            stripped = href.replace('/wiki/', '')
            if '/wiki/' in href and ':' not in href: #checks if the link is to another article (not list or something)
                lock.acquire()
                if stripped not in table: #if article has not been seen by anyone, add to queue
                    table[stripped] = node
                    seen[stripped] = True
                    queue.append(stripped)
                elif stripped not in seen: #otherwise, if this thread hasn't seen it, but the other has, we are done.
                    key = node
                    altpath = []
                    while key != '<None>': #traces article back to start page
                        altpath.insert(0, key)
                        key = table[key]
                    key = stripped
                    while key != '<None>': #traces article to end page
                        altpath.append(key)
                        key = table[key]
                    if len(altpath) < minlen: 
                        minlen = len(altpath)
                        path1.clear()
                        path1.extend(altpath)
                lock.release()

        if path1:
            return path1
    return None

#Performs BFS from the end article. This takes advantage of Wikipedia's "What Links Here" page 
def reversesearch(lock, table, start, path2):
    minlen = 100000
    queue = [start]
    seen = defaultdict(bool)
    seen[start] = True
    
    while queue:
        node = queue.pop(0)
        html = gettext(
            "https://en.wikipedia.org/w/index.php?title=Special:WhatLinksHere/" + node + "&namespace=0&limit=5000&hideredirs=1&hidetrans=1")
        if html is None:
            continue
        parsed = HTMLParser(html)
        div = parsed.css_first('[id=mw-whatlinkshere-list]')
        if div is None:
            continue
        #takes all links pointing to the article and adds them to the queue
        for tag in div.css('li'): 
            att = tag.css_first('a').attrs
            try:
                href = str(att['href'])
            except:
                continue
            stripped = href.replace('/wiki/', '')
            lock.acquire()
            if stripped not in table: #if article has not been seen by anyone, add to queue
                table[stripped] = node
                seen[stripped] = True
                queue.append(stripped)
            elif stripped not in seen: #otherwise, if this thread hasn't seen it, but the other has, we are done.
                key = node
                altpath = []
                while key != '<None>': #traces article back to end page
                    altpath.append(key)
                    key = table[key]
                key = stripped
                while key != '<None>': #traces article to start page
                    altpath.insert(0, key)
                    key = table[key]
                if len(altpath) < minlen:
                    minlen = len(altpath)
                    path2.clear()
                    path2.extend(altpath)
            lock.release()
        if path2:
            return path2
    return None

#takes start and end page, returns list of articles that connect the two
def main(star, en):
    start = star.replace(" ", "_")
    end = en.replace(" ", "_")
    if start == end:
        print("You input the same page twice :(")
        return [start]
    if verify_search(start, end) is False: # check if either article is nonexistent
        print("Articles are unsearchable")  
        return "Sorry, One or more of the pages you input did not exist or were impossible to navigate to."
        
    #3 tables: master table for all seen pages, and one for each thread to avoid cycles
    table = defaultdict(str)
    table[start] = '<None>'  # dictionary of links that point to their parent article
    table[end] = '<None>'  # dictionary of links that point to their parent article
    path1 = []
    path2 = []
    lock = Lock()
    s = Thread(group=None, target=search, args=(lock, table, start, path1))
    e = Thread(group=None, target=reversesearch, args=(lock, table, end, path2))
    s.start()
    e.start()
    s.join()
    e.join()
    if len(path1) <= len(path2):
        print(path1)
        return path1
    else:
        print(path2)
        return path2

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
