/* Native Linux harness: the real overlay source with Win32 stubbed, to exercise controller_tick. */
#define __stdcall
#define DllMain DllMain_unused
#include "overlay_llp64.c"
#include <stdio.h>
static int cur_x=500,cur_y=400,clicks_down=0,clicks_up=0,wheel=0,esc=0;static XPAD fake;static int fake_connected=1;
static DWORD __stdcall fake_get(DWORD i,XPAD*o){if(i!=0||!fake_connected)return 1167;*o=fake;return 0;}
BOOL __stdcall SetCursorPos(int x,int y){cur_x=x;cur_y=y;return 1;}
BOOL __stdcall GetCursorPos(POINT*p){p->x=cur_x;p->y=cur_y;return 1;}
void __stdcall mouse_event(DWORD f,DWORD a,DWORD b,DWORD d,unsigned long long e){if(f==2)clicks_down++;if(f==4)clicks_up++;if(f==0x800)wheel+=(int)d;}
BOOL __stdcall PostMessageA(HWND h,UINT m,WPARAM w,LPARAM l){if(m==WM_KEYDOWN&&w==VK_ESCAPE)esc++;return 1;}
BOOL __stdcall GetWindowRect(HWND h,RECT*r){r->left=0;r->top=0;r->right=1600;r->bottom=900;return 1;}
HWND __stdcall GetForegroundWindow(void){return (HWND)1;}
BOOL __stdcall InvalidateRect(HWND h,const RECT*r,BOOL e){return 1;}
HINSTANCE __stdcall LoadLibraryA(LPCSTR n){return 0;}
void* __stdcall GetProcAddress(HINSTANCE h,LPCSTR n){return 0;}
#define TICK(n) for(int _i=0;_i<(n);_i++) r+=controller_tick(1)
int main(){int r=0,fails=0;
 g_overlay=(HWND)1;g_phys_visible=1;g_xinit=1;g_xget=fake_get;g_ctrl_combo=0x00C0;
 /* combo L3+R3: one toggle on the rising edge only */
 fake.buttons=0x40;TICK(3);fake.buttons=0xC0;r=0;TICK(10);if(r!=1){printf("combo toggles=%d\n",r);fails++;}
 fake.buttons=0;TICK(2);
 /* full left-stick right for 50 ticks (~0.5 s) moves the cursor right ~1200 px, clamped to the window */
 fake.lx=32767;TICK(50);fake.lx=0;if(!(cur_x>=1500&&cur_x<=1598)){printf("stick x=%d\n",cur_x);fails++;}
 int before=cur_x;fake.lx=5000;TICK(50);fake.lx=0;if(cur_x!=before){printf("deadzone moved %d\n",cur_x-before);fails++;}
 /* stick up moves cursor up */
 before=cur_y;fake.ly=20000;TICK(20);fake.ly=0;if(!(cur_y<before)){printf("stick y %d->%d\n",before,cur_y);fails++;}
 /* A press/release -> exactly one down + one up; B -> Escape */
 fake.buttons=0x1000;TICK(5);fake.buttons=0;TICK(2);if(clicks_down!=1||clicks_up!=1){printf("A %d/%d\n",clicks_down,clicks_up);fails++;}
 fake.buttons=0x2000;TICK(5);fake.buttons=0;TICK(1);if(esc!=1){printf("B esc=%d\n",esc);fails++;}
 /* RB/LB switch tabs and wrap */
 g_tab=0;fake.buttons=0x0200;TICK(2);fake.buttons=0;TICK(1);fake.buttons=0x0100;TICK(2);fake.buttons=0;TICK(1);fake.buttons=0x0100;TICK(2);fake.buttons=0;TICK(1);
 if(g_tab!=3){printf("tab=%d\n",g_tab);fails++;} /* v1.24.21: 4 tabs */
 /* right stick down scrolls wheel negative */
 fake.ry=-32767;TICK(40);fake.ry=0;if(wheel>=0){printf("wheel=%d\n",wheel);fails++;}
 /* disabled: no movement, no toggle */
 g_ctrl_enabled=0;before=cur_x;fake.lx=-32767;fake.buttons=0xC0;r=0;TICK(20);fake.lx=0;fake.buttons=0;if(r||cur_x!=before){printf("disabled r=%d moved=%d\n",r,cur_x-before);fails++;}
 g_ctrl_enabled=1;
 /* overlay hidden: stick/A ignored, combo still opens (game focused) */
 g_phys_visible=0;before=cur_x;int cd=clicks_down;fake.lx=32767;fake.buttons=0x1000;TICK(10);fake.lx=0;fake.buttons=0;TICK(1);
 if(cur_x!=before||clicks_down!=cd){printf("hidden moved=%d clicks=%d\n",cur_x-before,clicks_down-cd);fails++;}
 fake.buttons=0xC0;r=0;TICK(3);fake.buttons=0;if(r!=1){printf("hidden combo=%d\n",r);fails++;}
 /* no controller connected: nothing happens */
 fake_connected=0;g_phys_visible=1;r=0;TICK(10);if(r){fails++;}

 /* 'cycle' setting kind steps through the published options and wraps */
 g_setting_count=1;scpy(g_settings[0].kind,"cycle",16);scpy(g_settings[0].value,"L3+R3",40);scpy(g_settings[0].original,"L3+R3",40);scpy(g_settings[0].recommended,"L3+R3;VIEW+MENU;VIEW+RB",64);
 adjust_setting(0,1);if(!seq(g_settings[0].value,"VIEW+MENU")){printf("cycle+ %s\n",g_settings[0].value);fails++;}
 adjust_setting(0,-1);adjust_setting(0,-1);if(!seq(g_settings[0].value,"VIEW+RB")){printf("cycle wrap %s\n",g_settings[0].value);fails++;}
 /* state keys parsed */
 char k1[]="CONTROLLER_ENABLED",v1[]="0",k2[]="CONTROLLER_COMBO",v2[]="544";setkv(k1,v1);setkv(k2,v2);
 if(g_ctrl_enabled!=0||g_ctrl_combo!=544){printf("setkv %d %u\n",g_ctrl_enabled,g_ctrl_combo);fails++;}
 printf(fails?"CONTROLLER HARNESS: FAIL (%d)\n":"CONTROLLER HARNESS: PASS\n",fails);return fails;}
