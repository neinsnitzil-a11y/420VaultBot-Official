from __future__ import annotations
import discord
from app.services.search import SearchService

def fmt_bytes(n:int)->str:
 units=['B','KB','MB','GB','TB']; x=float(n)
 for u in units:
  if x<1024 or u==units[-1]: return f'{x:.1f} {u}'
  x/=1024

class SearchResultsView(discord.ui.View):
 def __init__(self,service:SearchService,query:str,page_size:int,max_results:int,owner_id:int,extension:str|None=None):
  super().__init__(timeout=300); self.s=service; self.query=query; self.page_size=page_size; self.max_results=max_results; self.owner_id=owner_id; self.extension=extension; self.page=1
 def result(self): return self.s.search(self.query,self.page,self.page_size,self.extension,self.max_results)
 def embed(self):
  r=self.result(); e=discord.Embed(title='🔎 420Vault Search',description=f'Query: **{discord.utils.escape_markdown(self.query or "All files")}**\n{r.total:,} result(s)')
  if not r.items: e.add_field(name='No results',value='Try a broader search.',inline=False)
  for i,x in enumerate(r.items,1+(r.page-1)*r.page_size):
   e.add_field(name=f'{i}. {x["filename"]}',value=f'`ID {x["id"]}` • {fmt_bytes(x["file_size"])} • `{x["folder"] or "/"}`',inline=False)
  e.set_footer(text=f'Page {r.page}/{r.pages} • {self.page_size} per page'); return e
 async def interaction_check(self,i):
  if i.user.id!=self.owner_id: await i.response.send_message('This search panel belongs to another user. Run `420_search` for your own.',ephemeral=True); return False
  return True
 @discord.ui.button(label='Previous',emoji='◀️',style=discord.ButtonStyle.secondary)
 async def prev(self,i,b): self.page=max(1,self.page-1); await i.response.edit_message(embed=self.embed(),view=self)
 @discord.ui.button(label='Next',emoji='▶️',style=discord.ButtonStyle.secondary)
 async def next(self,i,b): self.page=min(self.result().pages,self.page+1); await i.response.edit_message(embed=self.embed(),view=self)
 @discord.ui.button(label='Close',emoji='✖️',style=discord.ButtonStyle.danger)
 async def close(self,i,b): self.stop(); await i.response.edit_message(view=None)
