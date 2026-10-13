/* v1.24.22: negative one-decimal setting values keep their sign; NEXT PS header. */
#define __stdcall
#define DllMain DllMain_unused
#include "overlay_llp64.c"
#include <stdio.h>
BOOL __stdcall InvalidateRect(HWND h,const RECT*r,BOOL e){return 1;}
static Setting* mk(const char*val){Setting*s=&g_settings[0];for(unsigned z=0;z<sizeof(Setting);z++)((BYTE*)s)[z]=0;scpy(s->kind,"float",sizeof(s->kind));scpy(s->value,val,sizeof(s->value));scpy(s->minv,"-2.0",sizeof(s->minv));scpy(s->maxv,"2.0",sizeof(s->maxv));scpy(s->step,"0.5",sizeof(s->step));g_setting_count=1;return s;}
int main(){int fails=0;
 Setting*s=mk("0.0");
 adjust_setting(0,-1); if(!seq(s->value,"-0.5")){printf("0 - 0.5 -> %s\n",s->value);fails++;}
 adjust_setting(0,-1); if(!seq(s->value,"-1.0")){printf("-0.5 - 0.5 -> %s\n",s->value);fails++;}
 adjust_setting(0,-1);adjust_setting(0,-1);adjust_setting(0,-1); if(!seq(s->value,"-2.0")){printf("clamp -> %s\n",s->value);fails++;}
 adjust_setting(0,1);adjust_setting(0,1);adjust_setting(0,1);adjust_setting(0,1); if(!seq(s->value,"0.0")){printf("back to 0 -> %s\n",s->value);fails++;}
 if(fails){printf("FAIL %d\n",fails);return 1;}
 printf("SETTINGS v1.24.22 HARNESS: PASS\n");return 0;}
