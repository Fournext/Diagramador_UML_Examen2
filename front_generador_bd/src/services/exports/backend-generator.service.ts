import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { saveAs } from 'file-saver';
import { environment } from '../../environments/environment';

@Injectable({ providedIn: 'root' })
export class BackendGeneratorService {

  constructor(private http: HttpClient) {}

  /**
   * Envía el JSON UML al backend y descarga el zip generado
   */
  generateBackend(json: any, filename: string = 'backend.zip') {
    this.http.post(`${environment.endpoint_java}generate`, json, {
      responseType: 'blob'
    }).subscribe({
      next: (zipBlob: Blob) => {
        saveAs(zipBlob, filename);
      },
      error: (err) => {
        console.error('Error generando backend:', err);
      }
    });
  }
}
