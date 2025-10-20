import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../environments/environment';

@Injectable({ providedIn: 'root' })
export class ChatbotService {
  constructor(private http: HttpClient) {}

  generateDiagram(prompt: string) {
    return this.http.post<any>(`${environment.endpoint_python}api/chatbot/`, { prompt });
  }
}
