/* v1.24.13: the real overlay load_state() fed with two files published by the real
   exporter (argv[1] = first publish, argv[2] = republish after Back + re-open). */
#define __stdcall
#define DllMain DllMain_unused
#include "overlay_llp64.c"
#include <stdio.h>
#include <stdlib.h>
static char *served=0; static unsigned served_len=0, fake_time=1;
static void serve(const char *path){FILE*f=fopen(path,"rb");fseek(f,0,SEEK_END);long n=ftell(f);fseek(f,0,SEEK_SET);free(served);served=malloc(n+1);served_len=(unsigned)fread(served,1,n,f);fclose(f);fake_time++;}
HANDLE __stdcall CreateFileA(LPCSTR n,DWORD a,DWORD s,void*sa,DWORD c,DWORD f,HANDLE t){return (HANDLE)7;}
DWORD __stdcall GetFileSize(HANDLE h,DWORD*hi){return served_len;}
BOOL __stdcall GetFileTime(HANDLE h,FILETIME*a,FILETIME*b,FILETIME*w){if(w){w->low=fake_time;w->high=0;}return 1;}
BOOL __stdcall ReadFile(HANDLE h,void*buf,DWORD n,DWORD*rd,void*o){if(n>served_len)n=served_len;for(DWORD i=0;i<n;i++)((char*)buf)[i]=served[i];*rd=n;return 1;}
BOOL __stdcall CloseHandle(HANDLE h){return 1;}
BOOL __stdcall InvalidateRect(HWND h,const RECT*r,BOOL e){return 1;}
DWORD __stdcall GetLastError(void){return 0;}
int main(int argc,char**argv){
 int pid=atoi(argv[3]);
 serve(argv[1]); load_state();
 if(!g_detail_valid||g_detail.id!=pid){printf("first publish did not show the player\n");return 1;}
 /* Back, then the same player again - exactly what the click handlers set */
 g_player_view=0;g_selected_pid=0;g_detail_valid=0;g_pending_pid=0;g_detail_loading=0;
 g_selected_pid=pid;g_pending_pid=pid;g_detail_valid=0;g_detail_loading=1;g_player_view=1;
 serve(argv[2]); int changed=load_state();
 printf("republish: changed=%d detail_valid=%d detail_loading=%d\n",changed,g_detail_valid,g_detail_loading);
 if(changed&&g_detail_valid&&!g_detail_loading&&g_detail.id==pid){printf("PASS\n");return 0;}
 printf("STUCK on LOADING PLAYER DETAILS\n");return 1;}
