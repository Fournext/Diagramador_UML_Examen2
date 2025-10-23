import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { environment } from '../../environments/environment';
import { Observable } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class UmlImageServiceTs {
  private baseUrl = environment.endpoint_python;
  private http = inject(HttpClient); // ej: 'http://localhost:8000/api'

  constructor() { }

  analyzeImage(file: File): Observable<any> {
    const formData = new FormData();
    formData.append('image', file);
    return this.http.post(`${this.baseUrl}api/uml_from_image/`, formData);
  }

}
