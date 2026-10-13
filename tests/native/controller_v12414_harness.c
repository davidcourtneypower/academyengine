/* v1.24.14: ring cursor and LT/RT sub-view switching, on the real overlay source. */
#define __stdcall
#define DllMain DllMain_unused
#include "overlay_llp64.c"
#include <stdio.h>
static int cur_x=500,cur_y=400,set_ring=0,made=0,cmds=0,clicks=0;static XPAD fake;
static HANDLE RING=(HANDLE)0x5151;
static DWORD __stdcall fake_get(DWORD i,XPAD*o){if(i!=0)return 1167;*o=fake;return 0;}
BOOL __stdcall SetCursorPos(int x,int y){cur_x=x;cur_y=y;return 1;}
BOOL __stdcall GetCursorPos(POINT*p){p->x=cur_x;p->y=cur_y;return 1;}
void __stdcall mouse_event(DWORD f,DWORD a,DWORD b,DWORD d,unsigned long long e){if(f==2)clicks++;}
BOOL __stdcall PostMessageA(HWND h,UINT m,WPARAM w,LPARAM l){return 1;}
BOOL __stdcall GetWindowRect(HWND h,RECT*r){r->left=0;r->top=0;r->right=1600;r->bottom=900;return 1;}
static HWND fg_win=(HWND)1;static int attach_ok=1,attached=0,synth=0,attach_calls=0;
HWND __stdcall GetForegroundWindow(void){return fg_win;}
BOOL __stdcall AttachThreadInput(DWORD a,DWORD b,BOOL on){attach_calls++;if(!attach_ok)return 0;attached=on?1:0;return 1;}
DWORD __stdcall GetCurrentThreadId(void){return 7;}
DWORD __stdcall GetWindowThreadProcessId(HWND h,LPDWORD p){if(p)*p=(h==(HWND)2)?4242:1;return h==(HWND)2?99:7;}
BOOL __stdcall BringWindowToTop(HWND h){return 1;}
void __stdcall keybd_event(BYTE vk,BYTE sc,DWORD f,unsigned long long e){if(vk==0x87&&!(f&2))synth=1;}
BOOL __stdcall SetForegroundWindow(HWND h){if(attached||synth){fg_win=h;return 1;}return 0;}
HWND __stdcall SetFocus(HWND h){return 0;}
BOOL __stdcall InvalidateRect(HWND h,const RECT*r,BOOL e){return 1;}
HANDLE __stdcall CreateCursor(HINSTANCE i,int hx,int hy,int w,int h,const void*a,const void*x){made++;return RING;}
HANDLE __stdcall SetCursor(HANDLE c){if(c==RING)set_ring++;return 0;}
HANDLE __stdcall CreateFileA(LPCSTR n,DWORD a,DWORD s,void*sa,DWORD c,DWORD f,HANDLE t){cmds++;return (HANDLE)-1;}
#define TICK(n) for(int _i=0;_i<(n);_i++) controller_tick(1)
#define TAP(bits) do{fake.buttons=0;fake.lt=fake.rt=0; if((bits)&0x10000)fake.lt=255; if((bits)&0x20000)fake.rt=255; fake.buttons=(WORD)((bits)&0xFFFF); TICK(3); fake.buttons=0;fake.lt=fake.rt=0; TICK(2);}while(0)
int main(){int fails=0;
 g_overlay=(HWND)1;g_phys_visible=1;g_xinit=1;g_xget=fake_get;g_ctrl_combo=0x00C0;g_model_generation=5;
 /* ring mask: centre dot and ring drawn, corners and the gap transparent */
 BYTE a[128],x[128];ring_masks(a,x);
 #define WHITE(px,py) (!(a[(py)*4+((px)>>3)]&(0x80>>((px)&7)))&&(x[(py)*4+((px)>>3)]&(0x80>>((px)&7))))
 #define CLEAR(px,py) ((a[(py)*4+((px)>>3)]&(0x80>>((px)&7)))&&!(x[(py)*4+((px)>>3)]&(0x80>>((px)&7))))
 if(!WHITE(15,15)||!WHITE(15,5)||!WHITE(25,15)||!CLEAR(0,0)||!CLEAR(31,31)||!CLEAR(15,10)){printf("ring mask wrong\n");fails++;}
 /* stick movement switches to the ring cursor */
 fake.lx=30000;TICK(5);fake.lx=0;TICK(1);
 if(!g_pad_cursor||!set_ring||made!=1){printf("ring not shown pad=%d set=%d made=%d\n",g_pad_cursor,set_ring,made);fails++;}
 /* WM_SETCURSOR over the client area keeps the ring */
 int before=set_ring;if(wndproc(g_overlay,0x0020,0,1)!=1||set_ring!=before+1){printf("WM_SETCURSOR not handled\n");fails++;}
 /* real mouse moves -> arrow returns (WM_SETCURSOR falls through to default) */
 cur_x+=37;TICK(1);if(g_pad_cursor){printf("real mouse did not restore arrow\n");fails++;}
 /* player details: RT next, LT previous, wrap */
 g_tab=1;g_player_view=1;g_selected_pid=460002;g_detail_tab=0;
 TAP(0x20000);if(g_detail_tab!=1){printf("RT detail_tab=%d\n",g_detail_tab);fails++;}
 TAP(0x20000);TAP(0x20000);if(g_detail_tab!=0){printf("RT wrap detail_tab=%d\n",g_detail_tab);fails++;}
 TAP(0x10000);if(g_detail_tab!=2){printf("LT wrap detail_tab=%d\n",g_detail_tab);fails++;}
 /* trigger held with another button: no switch */
 fake.lt=255;fake.buttons=0x1000;TICK(3);fake.buttons=0;fake.lt=0;TICK(2);if(g_detail_tab!=2){printf("LT+A switched to %d\n",g_detail_tab);fails++;}
 /* events tab: RT cycles the filter and sends the view command */
 g_player_view=0;g_selected_pid=0;g_tab=2;g_event_filter=0;g_filter_loading_ticks=0;int c0=cmds;
 TAP(0x20000);if(g_event_filter!=1||cmds==c0){printf("events RT filter=%d cmds=%d\n",g_event_filter,cmds-c0);fails++;}
 /* combo VIEW+LT+RT (open/close) never switches a sub-view */
 g_ctrl_combo=0x0020|0x10000|0x20000;g_filter_loading_ticks=0;int f0=g_event_filter;
 fake.buttons=0x0020;TICK(2);fake.lt=255;TICK(2);fake.rt=255;TICK(3);fake.rt=0;TICK(1);fake.lt=0;TICK(1);fake.buttons=0;TICK(2);
 if(g_event_filter!=f0){printf("combo changed filter to %d\n",g_event_filter);fails++;}
 /* v1.24.14b focus: overlay opened by the pad while FC27 (window 2) keeps the foreground */
 g_ctrl_combo=0x00C0;g_game=(HWND)2;g_pid=4242;
 fg_win=(HWND)2;attach_ok=1;attached=0;synth=0;force_foreground(g_overlay);
 if(fg_win!=g_overlay||synth){printf("attach path fg=%p synth=%d\n",(void*)fg_win,synth);fails++;}
 fg_win=(HWND)2;attach_ok=0;attached=0;synth=0;force_foreground(g_overlay);
 if(fg_win!=g_overlay||!synth){printf("fallback path fg=%p synth=%d\n",(void*)fg_win,synth);fails++;}
 /* recovery: overlay visible but not focused; the first press takes focus, sends no click */
 fg_win=(HWND)2;attach_ok=1;attached=0;synth=0;int c1=clicks;
 fake.buttons=0x1000;TICK(2);fake.buttons=0;TICK(2);
 if(fg_win!=g_overlay||clicks!=c1){printf("recovery fg=%p clicks=%d\n",(void*)fg_win,clicks-c1);fails++;}
 fake.buttons=0x1000;TICK(2);fake.buttons=0;TICK(2);if(clicks!=c1+1){printf("click after focus=%d\n",clicks-c1);fails++;}
 if(fails){printf("FAIL %d\n",fails);return 1;}
 printf("CONTROLLER v1.24.14 HARNESS: PASS\n");return 0;}
