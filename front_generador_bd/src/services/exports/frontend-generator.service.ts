import { inject, Injectable } from '@angular/core';
import { DiagramService } from '../diagram/diagram.service';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../environments/environment';
import { Observable } from 'rxjs';
import { saveAs } from 'file-saver';

@Injectable({
  providedIn: 'root'
})
export class FrontendGeneratorService {
  private http = inject(HttpClient);
  private API = environment.endpoint_python;

  constructor() { }

  generateFrontend(json: any, fileName: string = 'frontend.zip') {
    return this.http.post(`${this.API}api/generar_flutter/`, json, {
      responseType: 'blob'  // 👈 importante: recibir archivo binario
    }).subscribe({
      next: (zipBlob: Blob) => {
        console.log('Frontend generado con éxito');
        saveAs(zipBlob, fileName);
      },
      error: (error) => {
        console.error('Error al generar el frontend:', error);
      }
    });
  }


}
