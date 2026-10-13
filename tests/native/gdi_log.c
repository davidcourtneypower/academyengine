/* Logging GDI/Win32 stubs: the overlay's draw calls become text lines for a Pillow renderer. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef struct { int kind; unsigned color; int h; char path[300]; void* sel_bmp; void* brush; void* pen; void* font; unsigned text; } Obj;
static Obj objs[100000]; static int nobj=0;
static void* mk(int kind){ if(nobj>=99999) nobj=10; objs[nobj].kind=kind; objs[nobj].sel_bmp=0; return (void*)(long)(++nobj); }
static Obj* O(void* h){ long i=(long)h; return (i>0&&i<=nobj)?&objs[i-1]:0; }
static FILE* L(void){ static FILE* f=0; if(!f) f=fopen(getenv("GDI_LOG")?getenv("GDI_LOG"):"draw.log","w"); return f; }
void* CreateSolidBrush(unsigned c){ void* h=mk(1); O(h)->color=c; return h; }
void* CreatePen(int s,int w,unsigned c){ void* h=mk(2); O(h)->color=c; return h; }
void* CreateFontW(int h,int w,int e,int o,int weight,unsigned a,unsigned b,unsigned c,unsigned d,unsigned e2,unsigned f,unsigned g,unsigned i,const unsigned short* face){ void* x=mk(3); O(x)->h=h<0?-h:h; O(x)->color=weight; return x; }
void* CreateCompatibleDC(void* dc){ return mk(4); }
void* LoadImageA(void* inst,const char* path,unsigned t,int cx,int cy,unsigned fl){ FILE* f=fopen(path,"rb"); if(!f) return 0; fclose(f); void* h=mk(5); strncpy(O(h)->path,path,299); return h; }
static void* g_dc_brush=0,*g_dc_pen=0,*g_dc_font=0; static unsigned g_text=0xffffff;
void* SelectObject(void* dc,void* obj){ Obj* o=O(obj); Obj* d=O(dc); if(!o) return 0;
  if(d&&d->kind==4&&o->kind==5){ void* old=d->sel_bmp; d->sel_bmp=obj; return old; }
  void* old=0; if(o->kind==1){old=g_dc_brush; g_dc_brush=obj;} else if(o->kind==2){old=g_dc_pen; g_dc_pen=obj;} else if(o->kind==3){old=g_dc_font; g_dc_font=obj;} return old; }
int Rectangle(void* dc,int l,int t,int r,int b){ Obj* d=O(dc); if(d&&d->kind==4) return 1; fprintf(L(),"R %d %d %d %d %06x %06x\n",l,t,r,b,g_dc_brush?O(g_dc_brush)->color:0,g_dc_pen?O(g_dc_pen)->color:0); return 1; }
typedef struct { int left,top,right,bottom; } RECTi;
int FillRect(void* dc,const RECTi* r,void* br){ fprintf(L(),"R %d %d %d %d %06x %06x\n",r->left,r->top,r->right,r->bottom,O(br)?O(br)->color:0,O(br)?O(br)->color:0); return 1; }
unsigned SetTextColor(void* dc,unsigned c){ unsigned o=g_text; g_text=c; return o; }
int SetBkMode(void* dc,int m){ return 1; }
int MultiByteToWideChar(unsigned cp,unsigned fl,const char* s,int n,unsigned short* w,int cap){ int k=0; const unsigned char* p=(const unsigned char*)s; while(*p&&k<cap-1){ unsigned c=*p++; if(c>=0xE0){ c=((c&15)<<12)|((p[0]&63)<<6)|(p[1]&63); p+=2; } else if(c>=0xC0){ c=((c&31)<<6)|(p[0]&63); p++; } w[k++]=(unsigned short)c; } w[k]=0; return k+1; }
int DrawTextW(void* dc,const unsigned short* w,int n,RECTi* r,unsigned fl){ char out[4096]; int k=0; for(int i=0;w[i]&&k<4000;i++){ unsigned c=w[i]; if(c<0x80) out[k++]=c; else if(c<0x800){ out[k++]=0xC0|(c>>6); out[k++]=0x80|(c&63);} else { out[k++]=0xE0|(c>>12); out[k++]=0x80|((c>>6)&63); out[k++]=0x80|(c&63);} } out[k]=0;
  Obj* f=O(g_dc_font); fprintf(L(),"T %d %d %d %d %06x %u %d %d\t%s\n",r->left,r->top,r->right,r->bottom,g_text,fl,f?f->h:15,f?f->color:400,out); return 1; }
/* v1.0.4: text width. GDI_CHARW may name a file of 128 widths (1/100 px, ASCII, for a 15 px font) measured
   from the renderer's own font, so a test can check the layout against what is drawn; otherwise a rough table. */
typedef struct { int cx,cy; } SIZEi;
static int g_cw[128]; static int g_cw_loaded=0;
int GetTextExtentPoint32W(void* dc,const unsigned short* w,int n,SIZEi* sz){ Obj* f=O(g_dc_font); int h=f?f->h:15; long t=0;
  if(!g_cw_loaded){ g_cw_loaded=1; const char* p=getenv("GDI_CHARW"); FILE* cf=p?fopen(p,"r"):0; if(cf){ for(int i=0;i<128;i++) if(fscanf(cf,"%d",&g_cw[i])!=1) g_cw[i]=0; fclose(cf);} }
  for(int i=0;i<n;i++){ unsigned c=w[i]; if(c<128&&g_cw[c]>0){ t+=(long)g_cw[c]*h/15; continue; } int u; if(c==' '||c==','||c=='.'||c=='i'||c=='l'||c=='j'||c=='I'||c=='t'||c=='f'||c=='\''||c=='!') u=28; else if(c=='m'||c=='w'||c=='M'||c=='W') u=82; else if(c>='A'&&c<='Z') u=62; else if(c=='+') u=55; else u=52; t+=u*h; }
  sz->cx=(int)((t+99)/100); sz->cy=h; return 1; }
int BitBlt(void* dst,int x,int y,int w,int h,void* src,int sx,int sy,unsigned rop){ Obj* s=O(src); Obj* b=s?O(s->sel_bmp):0; if(b) fprintf(L(),"B %d %d %d %d\t%s\n",x,y,w,h,b->path); return 1; }
int DeleteObject(void* o){ return 1; } int DeleteDC(void* d){ return 1; }
int SaveDC(void* d){ return 1; } int RestoreDC(void* d,int i){ fprintf(L(),"U\n"); return 1; } int IntersectClipRect(void* d,int a,int b,int c,int e){ fprintf(L(),"C %d %d %d %d\n",a,b,c,e); return 1; }
int GetClientRect(void* h,RECTi* r){ r->left=0; r->top=0; r->right=atoi(getenv("VIZ_W")?getenv("VIZ_W"):"1600"); r->bottom=atoi(getenv("VIZ_H")?getenv("VIZ_H"):"900"); return 1; }
int InvalidateRect(void* h,const void* r,int e){ return 1; }
/* files: enough for load_state() */
void* CreateFileA(const char* p,unsigned a,unsigned s,void* sa,unsigned c,unsigned f,void* t){ FILE* fp=fopen(p,(a&0x80000000u)?"rb":"wb"); return fp?(void*)fp:(void*)-1; }
int WriteFile(void* h,const void* buf,unsigned n,unsigned* w,void* ov){ *w=(unsigned)fwrite(buf,1,n,(FILE*)h); return 1; }
int MoveFileExA(const char* a,const char* b,unsigned fl){ remove(b); return rename(a,b)==0; }
unsigned GetFileSize(void* h,unsigned* hi){ FILE* f=(FILE*)h; long c=ftell(f); fseek(f,0,SEEK_END); long n=ftell(f); fseek(f,c,SEEK_SET); return (unsigned)n; }
int GetFileTime(void* h,void* a,void* b,void* c){ return 0; }
int ReadFile(void* h,void* buf,unsigned n,unsigned* rd,void* ov){ *rd=(unsigned)fread(buf,1,n,(FILE*)h); return 1; }
int CloseHandle(void* h){ if(h&&h!=(void*)-1) fclose((FILE*)h); return 1; }
unsigned GetTickCount(void){ static unsigned t=1000; return t++; }
