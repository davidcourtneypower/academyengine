/* v1.24.31: gender / face keys, the read-only "info" setting kind and the faces section colour. */
#define __stdcall
#define DllMain DllMain_unused
#include "overlay_llp64.c"
#include <stdio.h>
static int pre(const char*a,const char*p){while(*p){if(*a++!=*p++)return 0;}return 1;}
static char*eqpos(char*s){while(*s&&*s!='=')s++;return *s?s:0;}
BOOL __stdcall InvalidateRect(HWND h,const RECT*r,BOOL e){return 1;}
static RECT cr={0,0,1600,900};
BOOL __stdcall GetClientRect(HWND h,RECT*r){*r=cr;return 1;}
int main(int argc,char**argv){int fails=0;g_overlay=(HWND)1;
 char k1[]="SELECTED_GENDER",v1[]="Female";setkv(k1,v1);
 if(!seq(g_sel_gender,"Female")){printf("gender %s\n",g_sel_gender);fails++;}
 char k2[]="SELECTED_FACE",v2[]="C:\\Users\\x\\AppData\\Local\\FC27AcademyEngine\\face_cache\\abc.bmp";setkv(k2,v2);
 if(!seq(g_sel_face,v2)){printf("face %s\n",g_sel_face);fails++;}
 /* the state file from the real exporter */
 if(argc>1){FILE*f=fopen(argv[1],"rb");char line[4096];int seen_info=0;g_setting_count=0;g_group_count=0;
  int in_settings=0;while(f&&fgets(line,sizeof line,f)){int n=slen(line);while(n&&(line[n-1]=='\n'||line[n-1]=='\r'))line[--n]=0;
   if(seq(line,"SETTINGS_BEGIN")){in_settings=1;continue;}if(seq(line,"SETTINGS_END")){in_settings=0;continue;}
   if(in_settings){parse_setting(line);continue;}
   char*eq=eqpos(line);if(eq&&(pre(line,"SELECTED_GENDER=")||pre(line,"SELECTED_FACE="))){*eq=0;setkv(line,eq+1);}}
  if(f)fclose(f);
  if(!seq(g_sel_gender,"Male")){printf("file gender %s\n",g_sel_gender);fails++;}
  if(!g_sel_face[0]){printf("file face empty\n");fails++;}
  for(int i=0;i<g_setting_count;i++){Setting*s=&g_settings[i];if(seq(s->kind,"info")){seen_info=1;char before[40];scpy(before,s->value,40);adjust_setting(i,1);if(!seq(before,s->value)||s->dirty){printf("info changed\n");fails++;}}}
  int fg=-1;for(int i=0;i<g_group_count;i++)if(seq(g_groups[i].id,"faces"))fg=i;
  if(!seen_info||fg<0){printf("faces section missing info=%d group=%d\n",seen_info,fg);fails++;}
  int en=setting_index_key("face_enabled");if(en<0||!seq(g_settings[en].kind,"bool")){printf("face_enabled\n");fails++;}
 }
 if(group_color("faces")==group_color("appearance")||group_color("faces")==C_ACCENT){printf("faces colour\n");fails++;}
 if(fails){printf("FAIL %d\n",fails);return 1;}
 printf("FACES v1.24.31 HARNESS: PASS\n");return 0;}
