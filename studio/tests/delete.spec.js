import { test, expect } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { randomUUID } from 'node:crypto';
const ids=Array.from({length:4},()=>randomUUID().replaceAll('-',''));
const seed=`import sys,json,sqlite3,time,shutil,os
from pathlib import Path
root=Path.home()/'.local/share/local-image-ai-service-images/studio'
db=sqlite3.connect(root/'history.sqlite3')
row=db.execute("SELECT data FROM records WHERE kind='image' LIMIT 1").fetchone()
source=json.loads(row[0])
for i,identifier in enumerate(sys.argv[1:]):
 path=root/(identifier+'.png')
 with (root/(source['id']+'.png')).open('rb') as src,path.open('xb') as dst:shutil.copyfileobj(src,dst)
 path.chmod(0o600)
 if source.get('pixel'):
  native=root/(identifier+'.pixels.png')
  with (root/(source['id']+'.pixels.png')).open('rb') as src,native.open('xb') as dst:shutil.copyfileobj(src,dst)
  native.chmod(0o600)
 item=json.loads(json.dumps(source));item.update(id=identifier,created=time.time()+i,favorite=False)
 item['request']['prompt']='Delete regression fixture '+str(i)
 job=dict(id=identifier,created=item['created'],status='completed',request=item['request'],image_id=identifier)
 db.execute('INSERT INTO records VALUES (?,?,?)',(identifier,'image',json.dumps(item)))
 db.execute('INSERT INTO records VALUES (?,?,?)',(identifier,'job',json.dumps(job)))
db.commit();db.close()`;
test.beforeAll(()=>execFileSync('python3',['-c',seed,...ids]));
test.afterAll(async({request})=>{for(const id of ids){const r=await request.delete('/studio/api/gallery/'+id);expect([200,404]).toContain(r.status());}});
test('cancel, single deletion, compare, select all and bulk deletion',async({page})=>{
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const initial=(await(await page.request.get('/studio/api/gallery')).json()).filter(i=>!ids.includes(i.id)).map(i=>i.id);
 // Display only disposable fixtures. The API and deletions still use the real service.
 await page.route('**/studio/api/gallery**',async route=>{
  if(route.request().method()==='GET'&&new URL(route.request().url()).pathname==='/studio/api/gallery'){
   const response=await route.fetch();const rows=await response.json();await route.fulfill({response,json:rows.filter(i=>ids.includes(i.id))});
  }else await route.continue();
 });
 await page.goto('/studio/');await expect(page.locator('.card')).toHaveCount(4);
 const single=page.locator(`[data-image-id="${ids[3]}"]`);
 await single.locator('.delete-card').click();await expect(page.locator('#delete-confirm')).toBeVisible();
 await expect(page.locator('#delete-title')).toHaveText('Delete image?');
 await expect(page.locator('#delete-description')).toHaveText('The PNG and its saved settings will be permanently deleted.');
 await page.locator('#delete-cancel').click();expect((await page.request.get('/studio/api/files/'+ids[3])).status()).toBe(200);
 await single.locator('button').first().click();await page.locator('#delete-image').click();
 await expect(page.locator('#metadata')).toContainText('"Settings"');
 await expect(page.locator('#metadata')).not.toContainText('Bilder kommerziell nutzbar');
 await page.locator('#delete-confirm-button').click();await expect(single).toHaveCount(0);
 expect((await page.request.get('/studio/api/files/'+ids[3])).status()).toBe(404);
 await expect(page.locator('#detail')).not.toBeVisible();
 await page.locator('.select-image').nth(0).check();await page.locator('.select-image').nth(1).check();
 await page.locator('#compare').click();await expect(page.locator('#comparison-images img')).toHaveCount(2);
 await page.locator('[data-close=comparison]').click();
 await page.locator('#select-all').click();await expect(page.locator('#selection-count')).toHaveText('3 selected');
 await page.locator('#clear-selection').click();await expect(page.locator('#selection-count')).toHaveText('0 selected');
 await page.locator('#select-all').click();await page.locator('#delete-selected').click();
 await expect(page.locator('#delete-title')).toHaveText('Delete 3 images?');
 await page.locator('#delete-confirm-button').click();await expect(page.locator('.card')).toHaveCount(0);
 await expect(page.locator('#selection-count')).toHaveText('0 selected');
 await expect(page.locator('#download')).not.toBeVisible();
 for(const id of ids)expect((await page.request.get('/studio/api/files/'+id)).status()).toBe(404);
 const remaining=(await(await page.request.get('/studio/api/gallery')).json()).map(i=>i.id);
 expect(initial.every(id=>remaining.includes(id))).toBeTruthy();
 await page.reload();await expect(page.locator('.card')).toHaveCount(0);
 // Let the final gallery interception finish before Playwright disposes its response context.
 await page.unrouteAll({behavior:'wait'});
 expect(errors).toEqual([]);
});
